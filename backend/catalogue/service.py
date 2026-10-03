"""Look up the rule that governs a licence type for a substance or class, and the approval
threshold that decides who gives final approval."""

from decimal import Decimal

from catalogue.models import (
    ApprovalThreshold,
    ApprovalThresholdVersion,
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


def substance_overrides(
    licence_type: LicenceType, substance_class: SubstanceClass
) -> list[LicenceTypeRuleVersion]:
    """Latest versions of this type's substance-specific rules for substances in the class."""
    rules = LicenceTypeRule.objects.filter(
        licence_type=licence_type, substance__substance_class=substance_class
    ).order_by("id")
    return [version for rule in rules if (version := _latest(rule)) is not None]


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


def latest_threshold(threshold: ApprovalThreshold | None) -> ApprovalThresholdVersion | None:
    if threshold is None:
        return None
    return threshold.versions.order_by("-version").first()


def resolve_threshold(substance: Substance) -> ApprovalThresholdVersion | None:
    """Substance threshold beats its class threshold. None means the officer alone approves."""
    specific = latest_threshold(ApprovalThreshold.objects.filter(substance=substance).first())
    if specific is not None:
        return specific
    return latest_threshold(
        ApprovalThreshold.objects.filter(substance_class=substance.substance_class_id).first()
    )


def add_threshold_version(
    *,
    substance: Substance | None = None,
    substance_class: SubstanceClass | None = None,
    superintendent_above_qty: Decimal,
    created_by: str,
) -> ApprovalThresholdVersion:
    threshold, _ = ApprovalThreshold.objects.get_or_create(
        substance=substance, substance_class=substance_class
    )
    # Lock the threshold row so concurrent additions can't compute the same version number.
    threshold = ApprovalThreshold.objects.select_for_update().get(pk=threshold.pk)
    latest = latest_threshold(threshold)
    return ApprovalThresholdVersion.objects.create(
        threshold=threshold,
        version=(latest.version + 1) if latest else 1,
        superintendent_above_qty=superintendent_above_qty,
        created_by=created_by,
    )


def approval_chain_for(substance: Substance, quantity: Decimal) -> str:
    """OFFICER_THEN_SUPERINTENDENT above the governing threshold, else OFFICER."""
    threshold = resolve_threshold(substance)
    if threshold is not None and quantity > threshold.superintendent_above_qty:
        return "OFFICER_THEN_SUPERINTENDENT"
    return "OFFICER"
