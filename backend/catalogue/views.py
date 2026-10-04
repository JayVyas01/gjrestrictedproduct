"""Read-only catalogue endpoints for any logged-in user."""

from rest_framework.response import Response
from rest_framework.views import APIView

from catalogue.models import ApprovalThreshold, LicenceType, LicenceTypeRule, SubstanceClass
from catalogue.service import class_unit, latest_rule_version, latest_threshold


def scope_of(row: ApprovalThreshold | LicenceTypeRule) -> dict:
    """Name, code, kind and unit of a rule's or threshold's scope (a substance or a class)."""
    if row.substance is not None:
        substance = row.substance
        return {
            "scope": substance.name,
            "scope_code": substance.code,
            "scope_kind": "substance",
            "unit": substance.unit,
        }
    substance_class = row.substance_class
    return {
        "scope": substance_class.name,
        "scope_code": substance_class.code,
        "scope_kind": "class",
        "unit": class_unit(substance_class),
    }


def _threshold_row(threshold: ApprovalThreshold) -> dict:
    latest = latest_threshold(threshold)
    scope = scope_of(threshold)
    return {
        "scope": scope["scope"],
        "scope_kind": scope["scope_kind"],
        "superintendent_above_qty": str(latest.superintendent_above_qty),
        "unit": scope["unit"],
        "version": latest.version,
    }


class ApprovalThresholdListView(APIView):
    """The latest version of every approval threshold."""

    def get(self, request):
        thresholds = (
            ApprovalThreshold.objects.select_related("substance", "substance_class")
            .filter(versions__isnull=False)
            .distinct()
            .order_by("id")
        )
        return Response([_threshold_row(threshold) for threshold in thresholds])


def _rule_row(rule: LicenceTypeRule) -> dict | None:
    latest = latest_rule_version(rule)
    if latest is None:
        return None
    return {
        **scope_of(rule),
        "version": latest.version,
        "may_buy": latest.may_buy,
        "may_sell": latest.may_sell,
        "may_transport": latest.may_transport,
        "max_stock_qty": str(latest.max_stock_qty),
        "max_per_transaction_qty": str(latest.max_per_transaction_qty),
        "validity_months": latest.validity_months,
    }


def _licence_type_row(licence_type: LicenceType) -> dict:
    rules = licence_type.rules.select_related("substance", "substance_class").order_by("id")
    return {
        "code": licence_type.code,
        "name": licence_type.name,
        "description": licence_type.description,
        "rules": [row for rule in rules if (row := _rule_row(rule)) is not None],
    }


class LicenceTypeListView(APIView):
    """Every licence type with the latest version of each of its rules."""

    def get(self, request):
        types = LicenceType.objects.order_by("code")
        return Response([_licence_type_row(licence_type) for licence_type in types])


class SubstanceClassListView(APIView):
    def get(self, request):
        classes = SubstanceClass.objects.order_by("code")
        return Response([{"code": c.code, "name": c.name, "unit": class_unit(c)} for c in classes])
