"""The buyer's own stock-limit rejection (Revision 4 §2). It raises no alert and is not counted
in the seller's rejection pattern."""

from django.db import migrations

KIND = "BUYER_REJECTION"
CODE = "STOCK_LIMIT"


def seed(apps, schema_editor):
    apps.get_model("reasons", "ReasonCode").objects.create(
        kind=KIND,
        code=CODE,
        label="This would take me over my licence's stock limit",
        sort_order=50,
    )


def unseed(apps, schema_editor):
    apps.get_model("reasons", "ReasonCode").objects.filter(kind=KIND, code=CODE).delete()


class Migration(migrations.Migration):
    dependencies = [("reasons", "0002_seed_defaults")]
    operations = [migrations.RunPython(seed, unseed)]
