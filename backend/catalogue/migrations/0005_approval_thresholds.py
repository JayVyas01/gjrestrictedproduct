"""Approval thresholds. Versions are append-only for everyone, including the table owner.

No row-level security: thresholds are reference data (ruling D-R12).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0004_rule_validity_positive"),
        ("core", "0002_append_only_guard"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalThreshold",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "substance",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="catalogue.substance",
                    ),
                ),
                (
                    "substance_class",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="catalogue.substanceclass",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ApprovalThresholdVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("version", models.PositiveIntegerField()),
                ("superintendent_above_qty", models.DecimalField(decimal_places=3, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.CharField(max_length=64)),
                (
                    "threshold",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="versions",
                        to="catalogue.approvalthreshold",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="approvalthreshold",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("substance__isnull", False), ("substance_class__isnull", True)),
                    models.Q(("substance__isnull", True), ("substance_class__isnull", False)),
                    _connector="OR",
                ),
                name="threshold_exactly_one_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalthreshold",
            constraint=models.UniqueConstraint(
                condition=models.Q(("substance__isnull", False)),
                fields=("substance",),
                name="one_threshold_per_substance",
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalthreshold",
            constraint=models.UniqueConstraint(
                condition=models.Q(("substance_class__isnull", False)),
                fields=("substance_class",),
                name="one_threshold_per_class",
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalthresholdversion",
            constraint=models.UniqueConstraint(
                fields=("threshold", "version"), name="unique_threshold_version"
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalthresholdversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("superintendent_above_qty__gt", 0)),
                name="threshold_qty_positive",
            ),
        ),
        migrations.RunSQL(
            sql="""
            REVOKE UPDATE, DELETE, TRUNCATE ON catalogue_approvalthresholdversion FROM gj_app;
            CREATE TRIGGER threshold_version_no_update_delete BEFORE UPDATE OR DELETE
              ON catalogue_approvalthresholdversion FOR EACH ROW
              EXECUTE FUNCTION reject_append_only_change();
            CREATE TRIGGER threshold_version_no_truncate BEFORE TRUNCATE
              ON catalogue_approvalthresholdversion FOR EACH STATEMENT
              EXECUTE FUNCTION reject_append_only_change();
            """,
            reverse_sql="""
            DROP TRIGGER threshold_version_no_truncate ON catalogue_approvalthresholdversion;
            DROP TRIGGER threshold_version_no_update_delete ON catalogue_approvalthresholdversion;
            GRANT UPDATE, DELETE ON catalogue_approvalthresholdversion TO gj_app;
            """,
        ),
    ]
