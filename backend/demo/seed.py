"""Play the scripted demo story (`demo/dataset.py`) through the real services, back in time.

Each event runs under `clock.at(moment)` in chronological order, acting as the person who
would really do it (`set_actor`, as the request middleware does), and calls the same service
the API would call. Codes for signed steps come from the demo SMS inbox, so every OTP is
issued and verified for real. The audit chain therefore records the whole history.

What has no service yet is created directly, and only during setup:
- reference data: areas, positions, substance classes, substances and the licence-type rule rows
  (a rule's versions and the thresholds do go through `catalogue.service`); and
- the officials' accounts (Licensing Authority, Head Authority, personnel), created with
  `User.objects.create_user` as `create_software_owner` does, each with a
  `demo.account_created` audit event. Licensee accounts go through the real enrolment.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from alerts.models import AuthorityAlert
from alerts.service import acknowledge
from audit.service import record
from catalogue.models import LicenceType, LicenceTypeRule, Substance, SubstanceClass, Unit
from catalogue.service import add_licence_type, add_rule_version, add_threshold_version
from core import crypto
from core.db_context import acting_as_system, set_actor
from demo import clock, dataset
from demo.dataset import Ago, HoursAgo, Step
from demo.models import DemoCredential, DemoInboxMessage, DemoPersona
from governance import service as governance
from identity.models import User
from licensing.enrolment import complete_enrolment, start_enrolment
from licensing.models import Licence
from licensing.service import find_by_number, record_licence, record_renewal, set_status
from oversight import service as oversight
from oversight.models import OversightBatch
from positions.models import Area, Position
from positions.service import assign, current_holder
from stock.service import set_opening_balance
from transactions import service as transactions
from transactions.models import Transaction

SEED_ACTOR = "seed_demo"


class SeedFailed(Exception):
    pass


def moment(when: Ago | HoursAgo) -> datetime:
    if isinstance(when, HoursAgo):
        return clock.hours_ago(when.hours)
    return clock.days_ago(when.days, when.time)


def _act_as(user: User) -> None:
    set_actor(user_id=user.user_id, role=user.role)


def _anonymous() -> None:
    set_actor(user_id="", role="")


def _latest_code(user_id: str) -> str:
    """The newest code the demo SMS inbox received for this account ("" = enrolment)."""
    return DemoInboxMessage.objects.filter(user_id=user_id).latest("id").code


@dataclass(frozen=True)
class Event:
    when: datetime
    run: Callable[[], None]


class Seeder:
    def __init__(self):
        self.password = settings.DEMO_PASSWORD
        self.accounts: dict[str, User] = {}  # official or business key -> account
        self.sales: dict[str, Transaction] = {}  # sale key -> transaction
        self.today = timezone.localdate()

    # --- the whole story -----------------------------------------------------------------

    def run(self) -> None:
        with clock.at(moment(dataset.SETUP)):
            self._catalogue()
            self._areas_and_positions()
            self._officials()
        with clock.at(moment(dataset.LICENCES_RECORDED)):
            self._licences()
        with clock.at(moment(dataset.OPENING_STOCK_RECORDED)):
            self._opening_stock()
        self._enrolments()
        for event in self._timeline():
            with clock.at(event.when):
                event.run()
        # The batch job once more for today, at the real time (as the scheduler would).
        self._batch_job()
        self._personas()
        self._credentials()

    def _timeline(self) -> list[Event]:
        events = [
            *self._review_period_events(),
            *self._nightly_batch_jobs(),
            *self._licence_change_events(),
            *self._sale_events(),
            *self._review_events(),
            *self._acknowledgement_events(),
            *self._proposal_events(),
        ]
        # sorted() is stable: events at the same moment keep the order above.
        return sorted(events, key=lambda event: event.when)

    # --- setup -------------------------------------------------------------------------------

    def _catalogue(self) -> None:
        classes = {
            code: SubstanceClass.objects.create(code=code, name=name)
            for code, name in dataset.SUBSTANCE_CLASSES
        }
        for code, name, class_code in dataset.SUBSTANCES:
            Substance.objects.create(
                code=code, name=name, substance_class=classes[class_code], unit=Unit.LITRE
            )
        for licence_type in dataset.LICENCE_TYPES:
            add_licence_type(
                code=licence_type.code,
                name=licence_type.name,
                description=licence_type.description,
            )
        by = SEED_ACTOR
        for rule in dataset.RULES:
            scope = (
                {"substance": Substance.objects.get(code=rule.substance)}
                if rule.substance
                else {"substance_class": classes[rule.substance_class]}
            )
            row, _ = LicenceTypeRule.objects.get_or_create(
                licence_type=self._licence_type(rule.licence_type), **scope
            )
            add_rule_version(
                row,
                created_by=by,
                may_buy=rule.may_buy,
                may_sell=rule.may_sell,
                may_transport=rule.may_transport,
                max_stock_qty=Decimal(rule.max_stock),
                max_per_transaction_qty=Decimal(rule.max_per_sale),
                validity_months=rule.validity_months,
            )
        for threshold in dataset.THRESHOLDS:
            add_threshold_version(
                substance=Substance.objects.get(code=threshold.substance),
                superintendent_above_qty=Decimal(threshold.above_litres),
                created_by=by,
            )

    @staticmethod
    def _licence_type(code: str) -> LicenceType:
        return LicenceType.objects.get(code=code)

    def _areas_and_positions(self) -> None:
        for code, name, level, parent in dataset.AREAS:
            Area.objects.create(
                code=code,
                name=name,
                level=level,
                parent=Area.objects.get(code=parent) if parent else None,
            )
        for code, title, area in dataset.POSITIONS:
            Position.objects.create(code=code, title=title, area=Area.objects.get(code=area))

    def _officials(self) -> None:
        for official in dataset.OFFICIALS:
            user = User.objects.create_user(
                role=official.role,
                password=self.password,
                contact=official.contact,
                email=official.email,
                must_change_password=True,  # an issued password (A3)
            )
            record(
                action="demo.account_created",
                actor=SEED_ACTOR,
                subject_type="user",
                subject_id=user.user_id,
            )
            self.accounts[official.key] = user
        assigner = self.accounts[dataset.ASSIGNED_BY]
        _act_as(assigner)
        for official in dataset.OFFICIALS:
            for code in official.positions:
                assign(
                    Position.objects.get(code=code),
                    self.accounts[official.key],
                    by=assigner.user_id,
                )

    def _licensing_authority(self) -> User:
        authority = self.accounts[dataset.LICENSING_AUTHORITY]
        _act_as(authority)
        return authority

    def _licences(self) -> None:
        authority = self._licensing_authority()
        for business in dataset.BUSINESSES:
            for licence in business.licences:
                record_licence(
                    number=licence.number,
                    gstin=business.gstin,
                    holder_name=business.name,
                    contact=business.contact,
                    licence_type=self._licence_type(licence.licence_type),
                    area=Area.objects.get(code=business.area),
                    starts_on=self.today - timedelta(days=licence.valid_from_days_ago),
                    ends_on=self.today + timedelta(days=licence.valid_until_days_ahead),
                    recorded_by=authority.user_id,
                    substance_class=SubstanceClass.objects.get(code=licence.substance_class),
                )

    def _opening_stock(self) -> None:
        authority = self._licensing_authority()
        for business in dataset.BUSINESSES:
            gstin_index = self._licence(business.licences[0].number).gstin_index
            for code, litres in business.opening_stock.items():
                with acting_as_system("opening_balance"):
                    set_opening_balance(
                        gstin_index=gstin_index,
                        substance=Substance.objects.get(code=code),
                        quantity=Decimal(litres),
                        by=authority.user_id,
                    )

    def _enrolments(self) -> None:
        """Each business with an account enrols as a real one would: licence number and GSTIN,
        then the code sent to the contact on file, then a password."""
        start = moment(dataset.ENROLMENTS_START)
        enrolling = [business for business in dataset.BUSINESSES if business.enrolled]
        for hour, business in enumerate(enrolling):
            with clock.at(start + timedelta(hours=hour)):
                _anonymous()
                challenge = start_enrolment(
                    licence_number=business.licences[0].number, gstin=business.gstin
                )
                if challenge is None:
                    raise SeedFailed(f"Enrolment refused for {business.name}")
                user = complete_enrolment(
                    challenge_id=str(challenge.public_id),
                    code=_latest_code(""),
                    password=self.password,
                )
                if user is None:
                    raise SeedFailed(f"Enrolment code refused for {business.name}")
                self.accounts[business.key] = user

    def _licence(self, number: str) -> Licence:
        with acting_as_system("seed_demo_lookup"):
            return find_by_number(number)

    # --- review periods, batches and licence changes ---------------------------------------

    def _review_period_events(self) -> list[Event]:
        def set_period(period=None):
            authority = self._licensing_authority()
            oversight.set_review_period(
                position=Position.objects.get(code=period.position),
                days=period.days,
                by=authority.user_id,
                starts_on=self.today - timedelta(days=period.starts_days_ago),
            )

        return [
            Event(moment(period.set_on), lambda period=period: set_period(period))
            for period in dataset.REVIEW_PERIODS
        ]

    def _batch_job(self) -> None:
        with acting_as_system("create_due_batches"):
            oversight.create_due_batches(timezone.localdate())

    def _nightly_batch_jobs(self) -> list[Event]:
        first = max(period.set_on.days for period in dataset.REVIEW_PERIODS) - 1
        return [
            Event(clock.days_ago(days, dataset.NIGHTLY_BATCH_JOB), self._batch_job)
            for days in range(first, 0, -1)
        ]

    def _licence_change_events(self) -> list[Event]:
        def renew(renewal):
            authority = self._licensing_authority()
            record_renewal(
                self._licence(renewal.licence),
                starts_on=self.today - timedelta(days=renewal.valid_from_days_ago),
                ends_on=self.today + timedelta(days=renewal.valid_until_days_ahead),
                recorded_by=authority.user_id,
            )

        def change_status(change):
            authority = self._licensing_authority()
            set_status(
                self._licence(change.licence),
                change.status,
                by=authority.user_id,
                reason=change.reason,
            )

        return [
            *(Event(moment(r.recorded), lambda r=r: renew(r)) for r in dataset.RENEWALS),
            *(Event(moment(c.when), lambda c=c: change_status(c)) for c in dataset.STATUS_CHANGES),
        ]

    # --- sales -------------------------------------------------------------------------------

    def _sale_events(self) -> list[Event]:
        events = []
        for number, sale in enumerate(dataset.SALES, start=1):
            steps = [Event(moment(sale.started), lambda sale=sale: self._start(sale))]
            for role in ("buyer", "officer", "superintendent"):
                step = getattr(sale, role)
                if step is not None:
                    steps.append(
                        Event(
                            moment(step.when),
                            lambda sale=sale, role=role, step=step: self._decide(sale, role, step),
                        )
                    )
            if sale.cancelled:
                steps.append(Event(moment(sale.cancelled), lambda sale=sale: self._cancel(sale)))
            times = [step.when for step in steps]
            if times != sorted(times) or len(set(times)) != len(times):
                raise SeedFailed(f"Sale {number} in the dataset has its steps out of order")
            events += steps
        return events

    def _sale_key(self, sale: dataset.Sale) -> str:
        return sale.key or f"sale-{dataset.SALES.index(sale)}"

    def _transport(self, sale: dataset.Sale) -> transactions.Transport:
        seller = self._business(sale.seller)
        buyer = self._business(sale.buyer_business)
        name, id_number, vehicle = seller.transporter
        return transactions.Transport(
            name=name,
            id_number=id_number,
            vehicle_number=vehicle,
            route=f"{seller.place} to {buyer.place}",
        )

    @staticmethod
    def _business(key: str) -> dataset.Business:
        return next(business for business in dataset.BUSINESSES if business.key == key)

    def _start(self, sale: dataset.Sale) -> None:
        seller = self.accounts[sale.seller]
        _act_as(seller)
        tx = transactions.start_transaction(
            seller=seller,
            buyer_gstin=self._business(sale.buyer_business).gstin,
            substance=Substance.objects.get(code=sale.substance),
            quantity=Decimal(sale.litres),
            transport=self._transport(sale),
        )
        self.sales[self._sale_key(sale)] = tx

    def _decider(self, tx: Transaction, sale: dataset.Sale, role: str) -> User:
        if role == "buyer":
            return self.accounts[sale.buyer_business]
        position = tx.designated_position if role == "officer" else tx.superintendent_position
        return current_holder(position)

    def _decide(self, sale: dataset.Sale, role: str, step: Step) -> None:
        tx = self.sales[self._sale_key(sale)]
        user = self._decider(tx, sale, role)
        _act_as(user)
        challenge = transactions.request_decision_code(reference=tx.reference, user=user)
        decided = transactions.decide(
            reference=tx.reference,
            user=user,
            challenge_id=str(challenge.public_id),
            code=_latest_code(user.user_id),
            outcome=step.outcome,
            reason_code=step.reason,
            comment=step.comment,
        )
        if decided is None:
            raise SeedFailed(f"The {role}'s code was refused for {tx.reference}")

    def _cancel(self, sale: dataset.Sale) -> None:
        seller = self.accounts[sale.seller]
        _act_as(seller)
        tx = self.sales[self._sale_key(sale)]
        transactions.cancel_transaction(reference=tx.reference, seller=seller)

    # --- batch reviews and alerts -------------------------------------------------------------

    def _review_events(self) -> list[Event]:
        events = []
        for review in dataset.BATCH_REVIEWS:
            for flag in review.flags:
                events.append(Event(moment(flag.when), lambda r=review, f=flag: self._flag(r, f)))
            events.append(Event(moment(review.signed), lambda r=review: self._sign(r)))
        return events

    def _reviewer(self, review: dataset.BatchReview) -> tuple[User, OversightBatch]:
        reviewer = current_holder(Position.objects.get(code=review.position))
        _act_as(reviewer)
        batch = OversightBatch.objects.get(
            position__code=review.position,
            period_start=self.today - timedelta(days=review.period_starts_days_ago),
        )
        return reviewer, batch

    def _flag(self, review: dataset.BatchReview, flag: dataset.Flag) -> None:
        reviewer, batch = self._reviewer(review)
        oversight.flag_item(
            batch_id=batch.id,
            reference=self.sales[flag.sale].reference,
            user=reviewer,
            reason_code=flag.reason,
            comment=flag.comment,
        )

    def _sign(self, review: dataset.BatchReview) -> None:
        reviewer, batch = self._reviewer(review)
        challenge = oversight.request_sign_off_code(batch_id=batch.id, user=reviewer)
        signed = oversight.sign_off(
            batch_id=batch.id,
            user=reviewer,
            challenge_id=str(challenge.public_id),
            code=_latest_code(reviewer.user_id),
        )
        if signed is None:
            raise SeedFailed(f"The sign-off code was refused for batch {batch.id}")

    def _acknowledgement_events(self) -> list[Event]:
        def acknowledge_alert(ack):
            officer = current_holder(Position.objects.get(code=ack.position))
            _act_as(officer)
            alert = AuthorityAlert.objects.get(
                transaction=self.sales[ack.sale], position__code=ack.position, kind=ack.kind
            )
            acknowledge(alert_id=alert.id, user=officer, note=ack.note)

        return [
            Event(moment(ack.when), lambda ack=ack: acknowledge_alert(ack))
            for ack in dataset.ACKNOWLEDGEMENTS
        ]

    # --- rule changes --------------------------------------------------------------------------

    def _proposal_events(self) -> list[Event]:
        drafted: dict[int, int] = {}  # index in PROPOSALS -> proposal id

        def draft(index, proposal):
            drafter = self.accounts[proposal.drafted_by]
            _act_as(drafter)
            drafted[index] = governance.draft(
                user=drafter,
                kind=proposal.kind,
                payload=proposal.payload,
                justification=proposal.justification,
            ).id

        def withdraw(index, proposal):
            drafter = self.accounts[proposal.drafted_by]
            _act_as(drafter)
            governance.withdraw(proposal_id=drafted[index], user=drafter)

        def decide(index, decision):
            head = self.accounts[decision.by]
            _act_as(head)
            challenge = governance.request_decision_code(proposal_id=drafted[index], user=head)
            decided = governance.decide(
                proposal_id=drafted[index],
                user=head,
                challenge_id=str(challenge.public_id),
                code=_latest_code(head.user_id),
                outcome=decision.outcome,
                note=decision.note,
            )
            if decided is None:
                raise SeedFailed("The rule-change decision code was refused")

        events = []
        for index, proposal in enumerate(dataset.PROPOSALS):
            events.append(Event(moment(proposal.drafted), lambda i=index, p=proposal: draft(i, p)))
            if proposal.withdrawn:
                events.append(
                    Event(moment(proposal.withdrawn), lambda i=index, p=proposal: withdraw(i, p))
                )
            if proposal.decision:
                events.append(
                    Event(
                        moment(proposal.decision.when),
                        lambda i=index, d=proposal.decision: decide(i, d),
                    )
                )
        return events

    # --- personas and passwords ------------------------------------------------------------

    def _personas(self) -> None:
        for persona in dataset.PERSONAS:
            account = self.accounts[dataset.PERSONA_ACCOUNTS[persona.key]]
            DemoPersona.objects.create(key=persona.key, user_id=account.user_id)

    def _credentials(self) -> None:
        """Every seeded account starts with the shared demo password (A7)."""
        DemoCredential.objects.bulk_create(
            DemoCredential(user_id=user.user_id, password_encrypted=crypto.encrypt(self.password))
            for user in self.accounts.values()
        )
