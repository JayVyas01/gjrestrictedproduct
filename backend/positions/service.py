"""Resolve positions by area and manage who currently holds them."""

from django.utils import timezone

from audit.service import record
from identity.models import User
from identity.roles import Role
from positions.models import Area, PersonnelAssignment, Position


def covering_position(area: Area, level: str) -> Position | None:
    """The position at `level` responsible for `area`, walking up to parent areas."""
    node = area
    while node is not None and node.level != level:
        node = node.parent
    if node is None:
        return None
    return Position.objects.filter(area=node, level=level).first()


def assign(position: Position, user: User, *, by: str) -> PersonnelAssignment:
    if user.role != Role.PERSONNEL:
        raise ValueError("Only Authorised Personnel can hold a position")
    now = timezone.now()
    PersonnelAssignment.objects.select_for_update().filter(
        position=position, ended_at__isnull=True
    ).update(ended_at=now)
    assignment = PersonnelAssignment.objects.create(position=position, user=user, started_at=now)
    record(
        action="position.assigned",
        actor=by,
        subject_type="position",
        subject_id=position.code,
        payload={"user_id": user.user_id},
    )
    return assignment


def current_holder(position: Position) -> User | None:
    assignment = (
        PersonnelAssignment.objects.select_related("user")
        .filter(position=position, ended_at__isnull=True)
        .first()
    )
    return assignment.user if assignment else None


def positions_held(user: User) -> list[Position]:
    return list(
        Position.objects.filter(
            assignments__user=user, assignments__ended_at__isnull=True
        ).order_by("code")
    )
