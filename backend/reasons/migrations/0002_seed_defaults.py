"""Default reason codes (spec D14). Admins may add more rows later; codes are never renamed."""

from django.db import migrations

DEFAULTS = {
    "OFFICER_REJECTION": [
        ("QUANTITY_MISMATCH", "Quantity mismatch (expected vs found)"),
        ("WEIGHT_MISMATCH", "Material weight mismatch"),
        ("TRANSPORTER_INVALID", "Transporter details invalid"),
        ("LICENCE_NOT_VALID", "Licence expired or not valid"),
    ],
    "BUYER_REJECTION": [
        ("NOT_ORDERED", "I did not place this order"),
        ("QUANTITY_WRONG", "Quantity does not match"),
        ("WRONG_SUBSTANCE", "Wrong substance"),
        ("TERMS_DISPUTE", "Terms dispute"),
    ],
    "SUPERINTENDENT_FLAG": [
        ("QUANTITY_UNUSUAL", "Quantity unusually high"),
        ("PATTERN_CONCERN", "Repeated pattern needs review"),
        ("TRANSPORT_CONCERN", "Transport details need checking"),
    ],
}


def seed(apps, schema_editor):
    ReasonCode = apps.get_model("reasons", "ReasonCode")
    for kind, rows in DEFAULTS.items():
        for order, (code, label) in enumerate(rows, start=1):
            ReasonCode.objects.create(kind=kind, code=code, label=label, sort_order=order * 10)
        ReasonCode.objects.create(
            kind=kind, code="OTHER", label="Other", requires_text=True, sort_order=999
        )


def unseed(apps, schema_editor):
    apps.get_model("reasons", "ReasonCode").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("reasons", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
