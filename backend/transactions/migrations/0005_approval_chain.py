"""Approval chain on transactions, the superintendent step, and wider status/step/outcome columns.

Existing rows get OFFICER. The column grant from 0002 stays UPDATE (status, decided_at): gj_app
can never change approval_chain.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0005_approval_thresholds"),
        ("licensing", "0005_licence_status_valid"),
        ("positions", "0002_one_position_per_area"),
        ("transactions", "0004_indexes"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="transaction",
            name="transaction_status_valid",
        ),
        migrations.AddField(
            model_name="transaction",
            name="approval_chain",
            field=models.CharField(
                choices=[
                    ("OFFICER", "Officer"),
                    ("OFFICER_THEN_SUPERINTENDENT", "Officer, then superintendent"),
                ],
                default="OFFICER",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="status",
            field=models.CharField(
                choices=[
                    ("AWAITING_BUYER", "Waiting for the buyer"),
                    ("AWAITING_OFFICER", "Waiting for the officer"),
                    ("AWAITING_SUPERINTENDENT", "Waiting for the superintendent"),
                    ("APPROVED", "Approved"),
                    ("REJECTED_BY_BUYER", "Rejected by the buyer"),
                    ("REJECTED_BY_OFFICER", "Rejected by the officer"),
                    ("REJECTED_BY_SUPERINTENDENT", "Rejected by the superintendent"),
                    ("CANCELLED", "Cancelled by the seller"),
                ],
                default="AWAITING_BUYER",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="transactiondecision",
            name="outcome",
            field=models.CharField(
                choices=[
                    ("CONFIRM", "Confirmed"),
                    ("APPROVE", "Approved"),
                    ("RECOMMEND", "Recommended for approval"),
                    ("REJECT", "Rejected"),
                    ("CANCEL", "Cancelled"),
                ],
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="transactiondecision",
            name="step",
            field=models.CharField(
                choices=[
                    ("BUYER", "Buyer"),
                    ("OFFICER", "Officer"),
                    ("SUPERINTENDENT", "Superintendent"),
                    ("SELLER", "Seller"),
                ],
                max_length=16,
            ),
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "status__in",
                        [
                            "AWAITING_BUYER",
                            "AWAITING_OFFICER",
                            "AWAITING_SUPERINTENDENT",
                            "APPROVED",
                            "REJECTED_BY_BUYER",
                            "REJECTED_BY_OFFICER",
                            "REJECTED_BY_SUPERINTENDENT",
                            "CANCELLED",
                        ],
                    )
                ),
                name="transaction_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("approval_chain__in", ["OFFICER", "OFFICER_THEN_SUPERINTENDENT"])
                ),
                name="transaction_chain_valid",
            ),
        ),
    ]
