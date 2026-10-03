import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("positions", "0002_one_position_per_area"),
        ("transactions", "0002_rls_and_append_only"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="superintendent_position",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="positions.position",
            ),
        ),
    ]
