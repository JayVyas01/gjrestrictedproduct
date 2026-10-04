"""The authority hierarchy. Authority belongs to positions, not people (spec: positional authority).

An assignment says who holds a position and from when to when. A transfer ends one
assignment and starts another; the position and its approval chains never change.
"""

from django.db import models

from identity.models import User


class AreaLevel(models.TextChoices):
    TALUKA = "TALUKA", "Taluka / area"
    DISTRICT = "DISTRICT", "District"
    STATE = "STATE", "State"


class Area(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=16, choices=AreaLevel.choices)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )

    def __str__(self) -> str:
        return self.name


class Position(models.Model):
    """The one approving position for an area; its level is the area's level.

    One position per area keeps routing deterministic. A second kind of position in the
    same area would later need a "kind" field (and uniqueness on area + kind).
    """

    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=120)
    area = models.OneToOneField(Area, on_delete=models.PROTECT, related_name="position")

    def __str__(self) -> str:
        return self.title


class PersonnelAssignment(models.Model):
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="assignments")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assignments")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["position"],
                condition=models.Q(ended_at__isnull=True),
                name="one_active_holder_per_position",
            ),
        ]
