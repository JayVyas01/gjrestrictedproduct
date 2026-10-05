"""The scripted demo story as data. Task 1: the persona list, in the order the picker shows."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    description: str


PERSONAS: tuple[Persona, ...] = (
    Persona(
        "seller",
        "Seller",
        "Sanand Spirits Pvt Ltd, a wholesale licensee in Sanand. Starts sales.",
    ),
    Persona(
        "buyer",
        "Buyer",
        "Bopal Bar & Kitchen, a retail licensee. Confirms or rejects incoming sales.",
    ),
    Persona(
        "area_officer",
        "Area Officer (Sanand)",
        "Approves or rejects sales from Sanand; recommends large ones upward.",
    ),
    Persona(
        "superintendent",
        "Superintendent (Ahmedabad)",
        "Gives final approval to large sales and reviews batches of decided sales.",
    ),
    Persona(
        "licensing_authority",
        "Licensing Authority",
        "Records licences, sets review periods and proposes rule changes.",
    ),
    Persona(
        "head_authority_a",
        "Head Authority A",
        "Oversees the whole state; drafts and decides rule changes.",
    ),
    Persona(
        "head_authority_b",
        "Head Authority B",
        "A second Head Authority, to approve rule changes the first one drafted.",
    ),
)
