"""Demo-only endpoints. Anonymous (codes, personas and sign-up are needed before sign-in), and
404 unless DEMO_MODE, exactly as if they did not exist. Only sign-up writes anything."""

from django.conf import settings
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from demo import signup
from demo.dataset import PERSONAS
from demo.models import DemoCredential, DemoInboxMessage, DemoPersona
from demo.serializers import SignupCompleteSerializer, SignupStartSerializer
from identity.login import login_identity
from identity.models import User

INBOX_SIZE = 20
SIGNUP_FAILED = "We couldn't match those details to a licensed business."


def _signup_failed() -> Response:
    return Response({"detail": SIGNUP_FAILED}, status=status.HTTP_401_UNAUTHORIZED)


class DemoView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "demo"  # its own budget: inbox polling must not use up "lookup"

    def initial(self, request, *args, **kwargs):
        # Before authentication and throttling, so the 404 looks the same for every request.
        if not settings.DEMO_MODE:
            raise Http404
        super().initial(request, *args, **kwargs)


class InboxView(DemoView):
    def get(self, request):
        messages = DemoInboxMessage.objects.order_by("-created_at", "-id")[:INBOX_SIZE]
        return Response(
            [
                {
                    "display_name": message.display_name,
                    "contact_last4": message.contact_last4,
                    "code": message.code,
                    "created_at": message.created_at,
                }
                for message in messages
            ]
        )


class PersonasView(DemoView):
    """Each seeded persona with what the sign-in form needs: the sign-in role, the identifier
    (a party's GSTIN or an official's email) and the password."""

    def get(self, request):
        seeded = dict(DemoPersona.objects.values_list("key", "user_id"))
        accounts = {user.user_id: user for user in User.objects.filter(user_id__in=seeded.values())}
        passwords = {
            credential.user_id: credential.password()
            for credential in DemoCredential.objects.filter(user_id__in=seeded.values())
        }
        entries = []
        for persona in PERSONAS:
            if persona.key not in seeded:
                continue
            user_id = seeded[persona.key]
            role, identifier = login_identity(accounts[user_id])
            entries.append(
                {
                    "key": persona.key,
                    "label": persona.label,
                    "description": persona.description,
                    "role": role,
                    "identifier": identifier,
                    # The current password; the seed's shared one until a row exists.
                    "password": passwords.get(user_id, settings.DEMO_PASSWORD),
                }
            )
        return Response(entries)


@method_decorator(csrf_protect, name="dispatch")
class SignupStartView(DemoView):
    """Party sign-up, step 1 (`demo/signup.py`): the code goes to the phone on file."""

    throttle_scope = "enrolment"  # the same budget as enrolment: both probe the register

    def post(self, request):
        data = SignupStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        challenge = signup.start_signup(**data.validated_data)
        if challenge is None:
            return _signup_failed()
        return Response({"challenge_id": str(challenge.public_id)})


@method_decorator(csrf_protect, name="dispatch")
class SignupCompleteView(DemoView):
    """Party sign-up, step 2: the code creates the account (not signed in yet)."""

    throttle_scope = "otp"

    def post(self, request):
        data = SignupCompleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = signup.complete_signup(
            challenge_id=str(data.validated_data["challenge_id"]),
            code=data.validated_data["code"],
        )
        if user is None:
            return _signup_failed()
        return Response({"user_id": user.user_id}, status=status.HTTP_201_CREATED)


class SignupCandidatesView(DemoView):
    """Licensed GSTINs not yet signed up, with their phone on file, so testers can pick one.
    Not audited, like the inbox: demo only, synthetic, and also listed in parties.csv."""

    def get(self, request):
        return Response(signup.candidates())
