"""HTTP endpoints for the transaction journey. Thin: validate, call a service, present.
Failures a user can fix are RETURNED (commit, e.g. a wrong code still counts); service
refusals raised inside a SYSTEM block have already rolled back their own writes."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from identity.permissions import role_required
from identity.roles import Role
from reasons.service import InvalidReason
from transactions.models import Transaction
from transactions.presenters import transaction_detail, transaction_summary
from transactions.serializers import (
    BuyerLookupSerializer,
    CheckTransactionSerializer,
    DecideSerializer,
    NewTransactionSerializer,
    TransactionFilterSerializer,
)
from transactions.service import (
    NotAllowed,
    TransactionRefused,
    Transport,
    cancel_transaction,
    check_transaction,
    decide,
    filter_transactions,
    find_buyer,
    load_visible,
    request_decision_code,
    start_transaction,
)

NO_BUYER = "No licensed business was found for this GSTIN. Check all 15 characters."
NOT_FOUND = {"detail": "Transaction not found."}
UNKNOWN_FILTER = {"detail": "Unknown filter value."}
WRONG_CODE = {"detail": "The code is wrong or has expired. Request a new code."}


def _refused(exc: TransactionRefused) -> Response:
    return Response(
        {"detail": "This transaction can't go ahead.", "reasons": exc.reasons},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def _forbidden(exc: Exception) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)


@method_decorator(csrf_protect, name="dispatch")
class BuyerLookupView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "lookup"

    def post(self, request):
        data = BuyerLookupSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        name = find_buyer(gstin=data.validated_data["gstin"], by=request.user)
        if name is None:
            return Response(
                {"detail": NO_BUYER},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"holder_name": name})


@method_decorator(csrf_protect, name="dispatch")
class CheckView(APIView):
    """Dry run before starting a sale: would it go ahead, and who would approve it."""

    permission_classes = [role_required(Role.LICENSEE)]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "lookup"

    def post(self, request):
        data = CheckTransactionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        reasons, chain = check_transaction(
            seller=request.user,
            buyer_gstin=v["buyer_gstin"],
            substance=v["substance"],
            quantity=v["quantity"],
        )
        return Response({"ok": not reasons, "reasons": reasons, "approval_chain": chain})


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [role_required(Role.LICENSEE)()]
        return super().get_permissions()

    def get(self, request):
        filters = TransactionFilterSerializer(data=request.query_params)
        if not filters.is_valid():
            return Response(UNKNOWN_FILTER, status=status.HTTP_400_BAD_REQUEST)
        rows = filter_transactions(
            Transaction.objects.select_related("substance"),
            request.user,
            **filters.validated_data,
        ).order_by("-created_at")[:50]
        return Response([transaction_summary(tx, request.user) for tx in rows])

    def post(self, request):
        data = NewTransactionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        transport = Transport(
            name=v["transporter_name"],
            id_number=v["transporter_id_number"],
            vehicle_number=v["vehicle_number"].upper().replace(" ", ""),
            route=v["route"],
        )
        try:
            tx = start_transaction(
                seller=request.user,
                buyer_gstin=v["buyer_gstin"],
                substance=v["substance"],
                quantity=v["quantity"],
                transport=transport,
            )
        except TransactionRefused as exc:
            return _refused(exc)
        return Response(
            transaction_detail(load_visible(tx.reference), request.user),
            status=status.HTTP_201_CREATED,
        )


class TransactionDetailView(APIView):
    def get(self, request, reference):
        tx = load_visible(reference)
        if tx is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(transaction_detail(tx, request.user))


class DecisionCodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, reference):
        try:
            challenge = request_decision_code(reference=reference, user=request.user)
        except NotAllowed as exc:
            return _forbidden(exc)
        return Response({"challenge_id": str(challenge.public_id)})


class DecideView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, reference):
        data = DecideSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            tx = decide(
                reference=reference,
                user=request.user,
                challenge_id=str(v["challenge_id"]),
                code=v["code"],
                outcome=v["outcome"],
                reason_code=v["reason_code"],
                comment=v["comment"],
            )
        except NotAllowed as exc:
            return _forbidden(exc)
        except InvalidReason as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except TransactionRefused as exc:
            return _refused(exc)
        if tx is None:
            return Response(WRONG_CODE, status=status.HTTP_401_UNAUTHORIZED)
        return Response(transaction_detail(load_visible(reference), request.user))


class CancelView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]

    def post(self, request, reference):
        try:
            cancel_transaction(reference=reference, seller=request.user)
        except NotAllowed as exc:
            return _forbidden(exc)
        return Response(transaction_detail(load_visible(reference), request.user))
