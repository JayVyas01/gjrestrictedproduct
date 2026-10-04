"""HTTP endpoints for licensing. Thin: validate, call a service, respond."""

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from catalogue.models import Substance
from identity.permissions import role_required
from identity.roles import Role
from licensing import register
from licensing.enrolment import complete_enrolment, start_enrolment
from licensing.models import Licence, LicenceStatus
from licensing.serializers import (
    EnrolmentCompleteSerializer,
    EnrolmentStartSerializer,
    RegisterSearchSerializer,
    licence_card,
)
from positions.models import Area

ENROLMENT_FAILED = (
    "We could not verify these details. "
    "Check the licence number and GSTIN exactly as printed on your licence."
)

UNKNOWN_FILTER = {"detail": "Unknown filter value."}
REGISTER_READERS = (Role.LICENSING_AUTHORITY, Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER)


def _failed() -> Response:
    return Response({"detail": ENROLMENT_FAILED}, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(csrf_protect, name="dispatch")
class EnrolmentStartView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "enrolment"

    def post(self, request):
        data = EnrolmentStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        challenge = start_enrolment(**data.validated_data)
        if challenge is None:
            return _failed()
        return Response({"challenge_id": str(challenge.public_id)})


@method_decorator(csrf_protect, name="dispatch")
class EnrolmentCompleteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        data = EnrolmentCompleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)  # weak password -> 400 before the code is used
        user = complete_enrolment(
            challenge_id=str(data.validated_data["challenge_id"]),
            code=data.validated_data["code"],
            password=data.validated_data["password"],
        )
        if user is None:
            return _failed()
        return Response({"user_id": user.user_id}, status=status.HTTP_201_CREATED)


class MyLicencesView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]

    def get(self, request):
        # Filtered here AND by row-level security (two independent checks).
        licences = (
            Licence.objects.select_related("licence_type", "substance", "substance_class")
            .filter(gstin_index=request.user.licensee_gstin_index)
            .order_by("id")
        )
        today = timezone.localdate()
        return Response([licence_card(licence, today) for licence in licences])


class SubstanceListView(APIView):
    def get(self, request):
        substances = Substance.objects.select_related("substance_class").order_by("name")
        return Response(
            [
                {
                    "code": s.code,
                    "name": s.name,
                    "substance_class": s.substance_class.name,
                    "unit": s.unit,
                }
                for s in substances
            ]
        )


MAX_REGISTER_PAGE = 10**6
# Licence numbers and GSTINs are searched only through POST bodies: in a query string they would
# end up in server and proxy logs. The GET listing refuses them rather than ignoring them.
URL_FORBIDDEN = {"number", "gstin"}


def _register_filters(params) -> dict:
    """The register's status, area and page filters, checked. Raises ValueError (or TypeError,
    for a JSON null or a list) for an unknown value."""
    page = int(params.get("page", 1))
    if not 1 <= page <= MAX_REGISTER_PAGE:  # a huge page would overflow the SQL OFFSET
        raise ValueError("page")
    status_filter = params.get("status")
    if status_filter is not None and status_filter not in LicenceStatus.values:
        raise ValueError("status")
    area_id = params.get("area")
    if area_id is not None:
        area_id = int(area_id)
        if not Area.objects.filter(pk=area_id).exists():
            raise ValueError("area")
    return {"status": status_filter, "area_id": area_id, "page": page}


def _register_page(user, filters: dict) -> Response:
    rows, total = register.search(user, **filters)
    return Response(
        {
            "count": total,
            "page": filters["page"],
            "page_size": register.PAGE_SIZE,
            "results": rows,
        }
    )


class LicenceRegisterView(APIView):
    """The register, filtered by status and area only (no search values in URLs)."""

    permission_classes = [role_required(*REGISTER_READERS)]

    def get(self, request):
        try:
            if URL_FORBIDDEN & request.query_params.keys():
                raise ValueError("search values belong in a POST body")
            filters = _register_filters(request.query_params)
        except (TypeError, ValueError):
            return Response(UNKNOWN_FILTER, status=status.HTTP_400_BAD_REQUEST)
        return _register_page(request.user, filters)


@method_decorator(csrf_protect, name="dispatch")
class LicenceSearchView(APIView):
    """The register's exact search by licence number or GSTIN, from the request body."""

    permission_classes = [role_required(*REGISTER_READERS)]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "lookup"

    def post(self, request):
        data = RegisterSearchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            filters = _register_filters(request.data)
        except (TypeError, ValueError):
            return Response(UNKNOWN_FILTER, status=status.HTTP_400_BAD_REQUEST)
        # A blank value is no search at all (the plain listing), not a search for "".
        filters["number"] = data.validated_data.get("number") or None
        filters["gstin"] = data.validated_data.get("gstin") or None
        return _register_page(request.user, filters)


class LicenceDetailView(APIView):
    permission_classes = [role_required(*REGISTER_READERS)]

    def get(self, request, licence_id: int):
        result = register.detail(request.user, licence_id)
        if result is None:
            return Response({"detail": "Licence not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result)
