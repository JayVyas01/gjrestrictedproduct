"""Look up the rule that governs a licence type for a substance or class."""

from decimal import Decimal

from catalogue.models import (
    LicenceType,
    LicenceTypeRule,
    LicenceTypeRuleVersion,
    Substance,
    SubstanceClass,
)


def _latest(rule: LicenceTypeRule | None) -> LicenceTypeRuleVersion | None:
    if rule is None:
        return None
    return rule.versions.order_by("-version").first()


def resolve_rule(
    licence_type: LicenceType,
    *,
    substance: Substance | None = None,
    substance_class: SubstanceClass | None = None,
) -> LicenceTypeRuleVersion | None:
    """Specific substance beats its class. No rule means the licence type is not permitted."""
    rules = LicenceTypeRule.objects.filter(licence_type=licence_type)
    if substance is not None:
        specific = _latest(rules.filter(substance=substance).first())
        if specific is not None:
            return specific
        substance_class = substance.substance_class
    if substance_class is None:
        return None
    return _latest(rules.filter(substance_class=substance_class).first())


def add_rule_version(
    rule: LicenceTypeRule,
    *,
    created_by: str,
    may_buy: bool,
    may_sell: bool,
    may_transport: bool,
    max_stock_qty: Decimal,
    max_per_transaction_qty: Decimal,
    validity_months: int,
) -> LicenceTypeRuleVersion:
    # Lock the rule row so concurrent additions can't compute the same version number.
    rule = LicenceTypeRule.objects.select_for_update().get(pk=rule.pk)
    latest = _latest(rule)
    return LicenceTypeRuleVersion.objects.create(
        rule=rule,
        version=(latest.version + 1) if latest else 1,
        created_by=created_by,
        may_buy=may_buy,
        may_sell=may_sell,
        may_transport=may_transport,
        max_stock_qty=max_stock_qty,
        max_per_transaction_qty=max_per_transaction_qty,
        validity_months=validity_months,
    )
