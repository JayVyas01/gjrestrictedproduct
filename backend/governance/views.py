"""HTTP endpoints for rule-change proposals. Thin: validate, call a service, present.

Refusals answer with fixed messages (each NotAllowed subclass carries its own constant), never
an exception's text. Failures RETURN a response so what must persist does (a wrong code still
counts; a failed apply's audit is kept); service writes refused inside a SYSTEM block have
already rolled back."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from governance.models import RuleChangeProposal
from governance.payloads import ProposalInvalid
from governance.presenters import proposal_view
from governance.serializers import DecideSerializer, DraftSerializer, ProposalFilterSerializer
from governance.service import (
    AlreadyDecided,
    NotADrafter,
    NotAllowed,
    NotHead,
    NotTheDrafter,
    OwnChange,
    ProposalNotFound,
    SomeoneElsesCode,
    UnknownOutcome,
    decide,
    draft,
    request_decision_code,
    withdraw,
)
from identity.permissions import role_required
from identity.roles import Role

UNKNOWN_FILTER = {"detail": "Unknown filter value."}
WRONG_CODE = {"detail": "The code is wrong or has expired. Request a new code."}
CANT_SAVE = "This rule change can't be saved."
NOT_ALLOWED = {"detail": NotAllowed.message}

# Each refusal's status and fixed body, built from the service's constants at import time.
_REFUSALS = {
    ProposalNotFound: (status.HTTP_404_NOT_FOUND, {"detail": ProposalNotFound.message}),
    AlreadyDecided: (status.HTTP_409_CONFLICT, {"detail": AlreadyDecided.message}),
    **{
        refusal: (status.HTTP_403_FORBIDDEN, {"detail": refusal.message})
        for refusal in (
            NotADrafter,
            NotTheDrafter,
            NotHead,
            OwnChange,
            UnknownOutcome,
            SomeoneElsesCode,
        )
    },
}


def _refused(exc: NotAllowed) -> Response:
    code, body = _REFUSALS.get(type(exc), (status.HTTP_403_FORBIDDEN, NOT_ALLOWED))
    return Response(body, status=code)


def _invalid(exc: ProposalInvalid) -> Response:
    return Response(
        {"detail": CANT_SAVE, "reasons": exc.reasons},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@method_decorator(csrf_protect, name="dispatch")
class ProposalListView(APIView):
    """Any logged-in user lists what row-level security lets them see; drafters draft."""

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            roles = (Role.LICENSING_AUTHORITY, Role.HEAD_AUTHORITY, Role.PERSONNEL)
            return [role_required(*roles)()]
        return super().get_permissions()

    def get(self, request):
        filters = ProposalFilterSerializer(data=request.query_params)
        if not filters.is_valid():
            return Response(UNKNOWN_FILTER, status=status.HTTP_400_BAD_REQUEST)
        rows = RuleChangeProposal.objects.order_by("-drafted_at", "-id")
        if filters.validated_data["status"]:
            rows = rows.filter(status=filters.validated_data["status"])
        return Response([proposal_view(p, request.user) for p in rows[:100]])

    def post(self, request):
        data = DraftSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            proposal = draft(
                user=request.user,
                kind=v["kind"],
                payload=v["payload"],
                justification=v["justification"],
            )
        except NotAllowed as exc:
            return _refused(exc)
        except ProposalInvalid as exc:
            return _invalid(exc)
        return Response(proposal_view(proposal, request.user), status=status.HTTP_201_CREATED)


class ProposalDetailView(APIView):
    def get(self, request, proposal_id):
        proposal = RuleChangeProposal.objects.filter(pk=proposal_id).first()
        if proposal is None:
            return Response({"detail": ProposalNotFound.message}, status=status.HTTP_404_NOT_FOUND)
        return Response(proposal_view(proposal, request.user))


@method_decorator(csrf_protect, name="dispatch")
class WithdrawView(APIView):
    def post(self, request, proposal_id):
        try:
            proposal = withdraw(proposal_id=proposal_id, user=request.user)
        except NotAllowed as exc:
            return _refused(exc)
        return Response(proposal_view(proposal, request.user))


@method_decorator(csrf_protect, name="dispatch")
class DecisionCodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, proposal_id):
        try:
            challenge = request_decision_code(proposal_id=proposal_id, user=request.user)
        except NotAllowed as exc:
            return _refused(exc)
        return Response({"challenge_id": str(challenge.public_id)})


@method_decorator(csrf_protect, name="dispatch")
class DecideView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, proposal_id):
        data = DecideSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            proposal = decide(
                proposal_id=proposal_id,
                user=request.user,
                challenge_id=str(v["challenge_id"]),
                code=v["code"],
                outcome=v["outcome"],
                note=v["note"],
            )
        except NotAllowed as exc:
            return _refused(exc)
        except ProposalInvalid as exc:
            return _invalid(exc)
        if proposal is None:
            return Response(WRONG_CODE, status=status.HTTP_401_UNAUTHORIZED)
        return Response(proposal_view(proposal, request.user))
