"""Plain-language checks for a proposed transaction. Each problem is one sentence the user can
act on. Run at creation and again at approval (stock may have changed in between)."""

from decimal import Decimal

from catalogue.models import Substance
from licensing.models import Licence
from licensing.service import current_permissions
from stock.service import balance_of


def fmt_qty(quantity: Decimal) -> str:
    return format(quantity.normalize(), "f")


def eligibility_problems(
    seller_licence: Licence | None, buyer_licence: Licence | None, substance: Substance
) -> list[str]:
    problems = []
    if seller_licence is None:
        problems.append(f"You have no valid licence that allows selling {substance.name}.")
    if buyer_licence is None:
        problems.append(f"This buyer has no valid licence that allows buying {substance.name}.")
    return problems


def transaction_problems(
    *, seller_licence: Licence, buyer_licence: Licence, substance: Substance, quantity: Decimal
) -> list[str]:
    unit = substance.unit
    q = fmt_qty(quantity)
    problems = []
    for licence, whose in ((seller_licence, "your"), (buyer_licence, "the buyer's")):
        limit = current_permissions(licence, substance).max_per_transaction_qty
        if quantity > limit:
            problems.append(
                f"Quantity {q} {unit} exceeds {whose} licence's per-transaction limit of "
                f"{fmt_qty(limit)} {unit}."
            )
    held = balance_of(seller_licence.gstin_index, substance)
    if quantity > held:
        problems.append(
            f"You have {fmt_qty(held)} {unit} of {substance.name} in stock, "
            f"which is less than {q} {unit}."
        )
    after = balance_of(buyer_licence.gstin_index, substance) + quantity
    buyer_max = current_permissions(buyer_licence, substance).max_stock_qty
    if after > buyer_max:
        problems.append(
            f"This sale would take the buyer's stock of {substance.name} "
            f"to {fmt_qty(after)} {unit}, "
            f"above their licence limit of {fmt_qty(buyer_max)} {unit}."
        )
    return problems
