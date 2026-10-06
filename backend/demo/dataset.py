"""The scripted demo story, as plain data. `seed_demo` plays it through the real services.

Everything here is synthetic: GSTINs use state code 99 (no real business has it), phone numbers
are in the reserved +91 98000 0xxxx range, licence numbers start with DEMO/ and officials'
emails use the reserved example domain. The places are real Gujarat districts and talukas:
Ahmedabad (Sanand, Daskroi, Bavla), Vadodara (Vadodara City, Padra) and Gandhinagar
(Gandhinagar, Kalol). Businesses marked `enrolled=False` are licensed but have no account yet,
so testers can try the demo sign-up with them.

How to read the dates: `Ago(12, "15:30")` means 12 days before the day the seed runs, at 15:30
India time, and `HoursAgo(3)` means 3 hours before the seed runs. The story covers the last 75
days. Past days are 2 or more days ago and today's events at most 6 hours ago, so the story
stays in order whatever time of day the seed runs. Quantities are litres.
"""

from dataclasses import dataclass, field

# --- How a moment and a step are written ---------------------------------------------------


@dataclass(frozen=True)
class Ago:
    days: int
    time: str = "10:00"


@dataclass(frozen=True)
class HoursAgo:
    hours: int


@dataclass(frozen=True)
class Step:
    """One decision on a sale: CONFIRM or REJECT (buyer); APPROVE, RECOMMEND or REJECT
    (officer); APPROVE or REJECT (superintendent). A rejection names a reason code."""

    outcome: str
    when: Ago | HoursAgo
    reason: str = ""
    comment: str = ""


# --- The personas (Task 1) -------------------------------------------------------------------


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
        "Bopal Bar & Kitchen, a hotel permit room. Confirms or rejects incoming sales.",
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

# Which seeded account plays each persona: an official's key or a business's key.
PERSONA_ACCOUNTS = {
    "seller": "sanand_spirits",
    "buyer": "bopal_bar",
    "area_officer": "area_officer",
    "superintendent": "superintendent",
    "licensing_authority": "licensing_authority",
    "head_authority_a": "head_authority_a",
    "head_authority_b": "head_authority_b",
}

# --- Catalogue: what can be traded, and under which licence types ----------------------------

SETUP = Ago(95, "10:00")  # the catalogue, areas, positions and officials exist from here on

SUBSTANCE_CLASSES = (("SPIRITS", "Spirits"), ("BEER", "Beer"), ("WINE", "Wine"))

# (code, name, class code); all measured in litres.
SUBSTANCES = (
    ("WHISKY", "Whisky", "SPIRITS"),
    ("RUM", "Rum", "SPIRITS"),
    ("VODKA", "Vodka", "SPIRITS"),
    ("BEER", "Beer", "BEER"),
    ("WINE", "Wine", "WINE"),
)


@dataclass(frozen=True)
class LicenceTypeData:
    code: str
    name: str
    description: str


# Placeholders until the Licensing Authority enters the real licence types.
LICENCE_TYPES = (
    LicenceTypeData("WHOLESALE", "Wholesale Distributor", "Buys, sells and moves stock in bulk."),
    LicenceTypeData("RETAIL", "Retail Vendor", "A shop that buys stock to sell to the public."),
    LicenceTypeData("HOTEL", "Hotel Permit Room", "A hotel bar that buys stock to serve guests."),
    LicenceTypeData("TRANSPORT", "Transport Carrier", "Moves stock for licensed businesses."),
)


@dataclass(frozen=True)
class Rule:
    """What a licence type may do with a class (or, as an override, one substance)."""

    licence_type: str
    may_buy: bool
    may_sell: bool
    may_transport: bool
    max_stock: int
    max_per_sale: int
    substance_class: str = ""
    substance: str = ""
    validity_months: int = 12


def _for_every_class(licence_type: str, **permissions) -> tuple[Rule, ...]:
    return tuple(
        Rule(licence_type, substance_class=code, **permissions) for code, _ in SUBSTANCE_CLASSES
    )


RULES = (
    *_for_every_class(
        "WHOLESALE",
        may_buy=True,
        may_sell=True,
        may_transport=True,
        max_stock=20000,
        max_per_sale=5000,
    ),
    *_for_every_class(
        "RETAIL",
        may_buy=True,
        may_sell=False,
        may_transport=False,
        max_stock=1000,
        max_per_sale=300,
    ),
    *_for_every_class(
        "HOTEL", may_buy=True, may_sell=False, may_transport=False, max_stock=500, max_per_sale=200
    ),
    *_for_every_class(
        "TRANSPORT",
        may_buy=False,
        may_sell=False,
        may_transport=True,
        max_stock=10000,
        max_per_sale=5000,
    ),
    # A rule for one substance beats its class rule: Retail Vendors may not buy or sell Rum.
    Rule(
        "RETAIL",
        substance="RUM",
        may_buy=False,
        may_sell=False,
        may_transport=False,
        max_stock=1000,
        max_per_sale=300,
    ),
)


@dataclass(frozen=True)
class Threshold:
    substance: str
    above_litres: int


# Above this quantity a sale also needs the district superintendent's final approval.
THRESHOLDS = (Threshold("WHISKY", 200),)

# --- Areas, positions and officials ----------------------------------------------------------

# (code, name, level, parent code)
AREAS = (
    ("GJ", "Gujarat", "STATE", ""),
    ("GJ-AHD", "Ahmedabad", "DISTRICT", "GJ"),
    ("GJ-AHD-SND", "Sanand", "TALUKA", "GJ-AHD"),
    ("GJ-AHD-DSK", "Daskroi", "TALUKA", "GJ-AHD"),
    ("GJ-AHD-BVL", "Bavla", "TALUKA", "GJ-AHD"),
    ("GJ-VAD", "Vadodara", "DISTRICT", "GJ"),
    ("GJ-VAD-VDC", "Vadodara City", "TALUKA", "GJ-VAD"),
    ("GJ-VAD-PDR", "Padra", "TALUKA", "GJ-VAD"),
    ("GJ-GNR", "Gandhinagar", "DISTRICT", "GJ"),
    ("GJ-GNR-GNR", "Gandhinagar", "TALUKA", "GJ-GNR"),
    ("GJ-GNR-KLL", "Kalol", "TALUKA", "GJ-GNR"),
)

# (code, title, area code): one approving position per district and taluka.
POSITIONS = (
    ("DO-AHD", "Superintendent, Ahmedabad", "GJ-AHD"),
    ("AO-SND", "Area Officer, Sanand", "GJ-AHD-SND"),
    ("AO-DSK", "Area Officer, Daskroi", "GJ-AHD-DSK"),
    ("AO-BVL", "Area Officer, Bavla", "GJ-AHD-BVL"),
    ("DO-VAD", "Superintendent, Vadodara", "GJ-VAD"),
    ("AO-VDC", "Area Officer, Vadodara City", "GJ-VAD-VDC"),
    ("AO-PDR", "Area Officer, Padra", "GJ-VAD-PDR"),
    ("DO-GNR", "Superintendent, Gandhinagar", "GJ-GNR"),
    ("AO-GNR", "Area Officer, Gandhinagar", "GJ-GNR-GNR"),
    ("AO-KLL", "Area Officer, Kalol", "GJ-GNR-KLL"),
)


@dataclass(frozen=True)
class Official:
    key: str
    role: str
    contact: str
    email: str  # the sign-in identifier; on the reserved example domain
    positions: tuple[str, ...] = ()


DEMO_EMAIL_DOMAIN = "demo.gujarat.example"


def _email(name: str) -> str:
    return f"{name}@{DEMO_EMAIL_DOMAIN}"


# Every district has a superintendent and every taluka an Area Officer. Officials' passwords
# are issued, so each must choose their own at the first sign-in (A3).
OFFICIALS = (
    Official(
        "licensing_authority",
        "LICENSING_AUTHORITY",
        "+919800000001",
        _email("licensing.authority"),
    ),
    Official("head_authority_a", "HEAD_AUTHORITY", "+919800000002", _email("head.a")),
    Official("head_authority_b", "HEAD_AUTHORITY", "+919800000003", _email("head.b")),
    Official("area_officer", "PERSONNEL", "+919800000011", _email("officer.sanand"), ("AO-SND",)),
    Official(
        "daskroi_officer", "PERSONNEL", "+919800000012", _email("officer.daskroi"), ("AO-DSK",)
    ),
    Official(
        "superintendent",
        "PERSONNEL",
        "+919800000013",
        _email("superintendent.ahmedabad"),
        ("DO-AHD",),
    ),
    Official(
        "vadodara_city_officer",
        "PERSONNEL",
        "+919800000014",
        _email("officer.vadodara-city"),
        ("AO-VDC",),
    ),
    Official(
        "vadodara_superintendent",
        "PERSONNEL",
        "+919800000015",
        _email("superintendent.vadodara"),
        ("DO-VAD",),
    ),
    Official("bavla_officer", "PERSONNEL", "+919800000016", _email("officer.bavla"), ("AO-BVL",)),
    Official("padra_officer", "PERSONNEL", "+919800000017", _email("officer.padra"), ("AO-PDR",)),
    Official(
        "gandhinagar_superintendent",
        "PERSONNEL",
        "+919800000018",
        _email("superintendent.gandhinagar"),
        ("DO-GNR",),
    ),
    Official(
        "gandhinagar_officer",
        "PERSONNEL",
        "+919800000019",
        _email("officer.gandhinagar"),
        ("AO-GNR",),
    ),
    Official("kalol_officer", "PERSONNEL", "+919800000020", _email("officer.kalol"), ("AO-KLL",)),
)

# Who records licences and opening stock, and who assigns officers to positions.
LICENSING_AUTHORITY = "licensing_authority"
ASSIGNED_BY = "head_authority_a"

# --- Businesses, their licences and opening stock ----------------------------------------------


@dataclass(frozen=True)
class LicenceData:
    """A class licence names a substance class (SPIRITS); a substance licence leaves the class
    blank and names one substance instead (substance="WHISKY")."""

    number: str
    licence_type: str
    substance_class: str
    valid_from_days_ago: int
    valid_until_days_ahead: int
    substance: str = ""


@dataclass(frozen=True)
class Business:
    key: str
    name: str
    gstin: str
    contact: str
    area: str
    place: str  # the town shown on transport routes
    licences: tuple[LicenceData, ...]
    opening_stock: dict[str, int] = field(default_factory=dict)
    enrolled: bool = True  # has a Licensee account (created through enrolment)
    transporter: tuple[str, str, str] = ("", "", "")  # name, ID, vehicle (for its sales)


LICENCES_RECORDED = Ago(92, "11:00")
OPENING_STOCK_RECORDED = Ago(90, "11:00")
ENROLMENTS_START = Ago(88, "10:00")  # one business enrols per hour from here

BUSINESSES = (
    Business(
        "sanand_spirits",
        "Sanand Spirits Pvt Ltd",
        "99AAECS1001A1Z5",
        "+919800000101",
        "GJ-AHD-SND",
        "Sanand",
        (LicenceData("DEMO/AHD/0001", "WHOLESALE", "SPIRITS", 300, 65),),
        {"WHISKY": 3000, "RUM": 800, "VODKA": 600},
        transporter=("Sabarmati Carriers", "GJ-TR-4411", "GJ01AB1234"),
    ),
    Business(
        "bopal_bar",
        "Bopal Bar & Kitchen",
        "99AAFCB2002B1Z6",
        "+919800000102",
        "GJ-AHD-DSK",
        "Bopal",
        (
            LicenceData("DEMO/AHD/0002", "HOTEL", "SPIRITS", 200, 165),
            LicenceData("DEMO/AHD/0003", "HOTEL", "BEER", 200, 165),
        ),
        # Close to its 500 L Whisky limit, so one more large Whisky sale is too much.
        {"WHISKY": 300, "RUM": 40, "VODKA": 30, "BEER": 200},
    ),
    Business(
        "bavla_liquor",
        "Bavla Liquor Store",
        "99AAGCB3003C1Z7",
        "+919800000103",
        "GJ-AHD-BVL",
        "Bavla",
        (LicenceData("DEMO/AHD/0004", "RETAIL", "SPIRITS", 250, 115),),
        {"WHISKY": 150, "VODKA": 100},
    ),
    Business(
        "sanand_retail",
        "Sanand Retail Wines",
        "99AAHCS4004D1Z8",
        "+919800000104",
        "GJ-AHD-SND",
        "Sanand",
        (
            LicenceData("DEMO/AHD/0005", "RETAIL", "SPIRITS", 180, 185),
            LicenceData("DEMO/AHD/0006", "RETAIL", "WINE", 180, 185),
        ),
        {"WHISKY": 200, "VODKA": 80, "WINE": 100},
    ),
    Business(
        "hotel_sabarmati",
        "Hotel Sabarmati Residency",
        "99AAJCH5005E1Z9",
        "+919800000105",
        "GJ-AHD-DSK",
        "Ahmedabad",
        # Expires in 20 days: shows on the Licensing Authority's "expiring soon" count.
        (LicenceData("DEMO/AHD/0007", "HOTEL", "SPIRITS", 345, 20),),
        {"WHISKY": 150, "RUM": 30},
    ),
    Business(
        "kanbha_traders",
        "Kanbha Traders",
        "99AAKCK6006F1Z1",
        "+919800000106",
        "GJ-AHD-DSK",
        "Kanbha",
        (LicenceData("DEMO/AHD/0008", "RETAIL", "SPIRITS", 220, 145),),  # suspended later
        {"WHISKY": 80},
    ),
    Business(
        "daskroi_beverages",
        "Daskroi Beverages LLP",
        "99AALCD7007G1Z2",
        "+919800000107",
        "GJ-AHD-DSK",
        "Daskroi",
        (LicenceData("DEMO/AHD/0009", "WHOLESALE", "BEER", 280, 85),),
        {"BEER": 6000},
        transporter=("Narmada Logistics", "GJ-TR-5120", "GJ01CD5678"),
    ),
    Business(
        "sabarmati_carriers",
        "Sabarmati Carriers",
        "99AAMCS8008H1Z3",
        "+919800000108",
        "GJ-AHD-SND",
        "Sanand",
        (LicenceData("DEMO/AHD/0010", "TRANSPORT", "SPIRITS", 160, 205),),
        enrolled=False,
    ),
    Business(
        "vadodara_distributors",
        "Vadodara Distributors Pvt Ltd",
        "99AANCV9009J1Z4",
        "+919800000109",
        "GJ-VAD-VDC",
        "Vadodara",
        (LicenceData("DEMO/VAD/0001", "WHOLESALE", "SPIRITS", 310, 55),),
        {"WHISKY": 2500, "RUM": 600, "VODKA": 400},
        transporter=("Vishwamitri Transport", "GJ-TR-6230", "GJ06EF9012"),
    ),
    Business(
        "padra_permit_room",
        "Padra Permit Room",
        "99AAPCP1010K1Z5",
        "+919800000110",
        "GJ-VAD-PDR",
        "Padra",
        # Its first period ends 16 days ago; a renewal (below) continues it.
        (LicenceData("DEMO/VAD/0002", "HOTEL", "SPIRITS", 380, -16),),
        {"WHISKY": 100, "RUM": 20, "VODKA": 20},
    ),
    Business(
        "padra_wholesale",
        "Padra Wholesale Beverages",
        "99AAUCP1015Q1Z1",
        "+919800000115",
        "GJ-VAD-PDR",
        "Padra",
        (LicenceData("DEMO/VAD/0003", "WHOLESALE", "SPIRITS", 260, 105),),
        {"WHISKY": 1500, "RUM": 300, "VODKA": 300},
        transporter=("Mahi Valley Transport", "GJ-TR-6345", "GJ06KL2345"),
    ),
    Business(
        "alkapuri_liquor",
        "Alkapuri Liquor Mart",
        "99AAVCA1016R1Z2",
        "+919800000116",
        "GJ-VAD-VDC",
        "Vadodara",
        # Expires in 12 days. A Retail Vendor: may not buy Rum (the Rum rule above).
        (LicenceData("DEMO/VAD/0004", "RETAIL", "SPIRITS", 210, 12),),
        {"WHISKY": 150, "VODKA": 50},
    ),
    # Gandhinagar district.
    Business(
        "gandhinagar_wholesale",
        "Gandhinagar Wholesale Traders",
        "99AAQCG1011L1Z6",
        "+919800000111",
        "GJ-GNR-GNR",
        "Gandhinagar",
        (
            LicenceData("DEMO/GNR/0001", "WHOLESALE", "SPIRITS", 230, 135),
            LicenceData("DEMO/GNR/0002", "WHOLESALE", "WINE", 230, 135),
        ),
        {"WHISKY": 2000, "RUM": 500, "VODKA": 500, "WINE": 800},
        transporter=("Capital Freight Services", "GJ-TR-7340", "GJ18GH3456"),
    ),
    Business(
        "kalol_beer_depot",
        "Kalol Beer Depot",
        "99AARCK1012M1Z7",
        "+919800000112",
        "GJ-GNR-KLL",
        "Kalol",
        (LicenceData("DEMO/GNR/0003", "WHOLESALE", "BEER", 200, 165),),
        {"BEER": 5000},
        transporter=("Kalol Roadways", "GJ-TR-7451", "GJ18JK7890"),
    ),
    Business(
        "infocity_hotel",
        "Hotel Infocity Grand",
        "99AASCH1013N1Z8",
        "+919800000113",
        "GJ-GNR-GNR",
        "Gandhinagar",
        (
            LicenceData("DEMO/GNR/0004", "HOTEL", "SPIRITS", 150, 215),
            LicenceData("DEMO/GNR/0005", "HOTEL", "BEER", 150, 215),
        ),
        {"WHISKY": 120, "BEER": 40},
    ),
    Business(
        "kalol_wine_shop",
        "Kalol Wine & Whisky Shop",
        "99AATCK1014P1Z9",
        "+919800000114",
        "GJ-GNR-KLL",
        "Kalol",
        # A class licence (all wine) and a substance licence (Whisky only): it may not buy Rum
        # or Vodka.
        (
            LicenceData("DEMO/GNR/0006", "RETAIL", "WINE", 120, 245),
            LicenceData("DEMO/GNR/0007", "RETAIL", "", 120, 245, substance="WHISKY"),
        ),
        {"WINE": 50},
    ),
    # Licensed but not signed up yet: candidates for the demo sign-up (with Sabarmati Carriers).
    Business(
        "bavla_beer_point",
        "Bavla Beer Point",
        "99AAWCB1017S1Z3",
        "+919800000117",
        "GJ-AHD-BVL",
        "Bavla",
        (LicenceData("DEMO/AHD/0011", "RETAIL", "BEER", 140, 225),),
        {"BEER": 300},
        enrolled=False,
    ),
    Business(
        "kathwada_inn",
        "Hotel Kathwada Inn",
        "99AAXCH1018T1Z4",
        "+919800000118",
        "GJ-AHD-DSK",
        "Kathwada",
        (LicenceData("DEMO/AHD/0012", "HOTEL", "SPIRITS", 100, 265),),
        {"WHISKY": 80},
        enrolled=False,
    ),
    Business(
        "sursagar_hotel",
        "Hotel Sursagar View",
        "99AAYCH1019U1Z5",
        "+919800000119",
        "GJ-VAD-VDC",
        "Vadodara",
        (LicenceData("DEMO/VAD/0005", "HOTEL", "SPIRITS", 130, 235),),
        {"WHISKY": 90, "RUM": 20},
        enrolled=False,
    ),
    Business(
        "sector21_wines",
        "Sector 21 Wine Shop",
        "99AAZCS1020V1Z6",
        "+919800000120",
        "GJ-GNR-GNR",
        "Gandhinagar",
        # Its spirits licence expired 10 days ago and was not renewed.
        (
            LicenceData("DEMO/GNR/0008", "RETAIL", "WINE", 160, 205),
            LicenceData("DEMO/GNR/0009", "RETAIL", "SPIRITS", 375, -10),
        ),
        {"WINE": 40},
        enrolled=False,
    ),
    Business(
        "padra_spirits_corner",
        "Padra Spirits Corner",
        "99ABACP1021W1Z7",
        "+919800000121",
        "GJ-VAD-PDR",
        "Padra",
        # Its beer licence is suspended; the spirits one is still active.
        (
            LicenceData("DEMO/VAD/0006", "RETAIL", "SPIRITS", 170, 195),
            LicenceData("DEMO/VAD/0007", "RETAIL", "BEER", 170, 195),
        ),
        {"WHISKY": 60},
        enrolled=False,
    ),
)


@dataclass(frozen=True)
class Renewal:
    licence: str
    recorded: Ago
    valid_from_days_ago: int
    valid_until_days_ahead: int


RENEWALS = (Renewal("DEMO/VAD/0002", Ago(20, "12:00"), 15, 350),)


@dataclass(frozen=True)
class StatusChange:
    licence: str
    status: str
    when: Ago
    reason: str


STATUS_CHANGES = (
    StatusChange(
        "DEMO/AHD/0008", "SUSPENDED", Ago(20, "16:00"), "Stock register not produced at inspection"
    ),
    StatusChange("DEMO/VAD/0007", "SUSPENDED", Ago(10, "16:30"), "Beer sold after hours"),
)

# --- Review periods: how often each district superintendent reviews approved sales ------------


@dataclass(frozen=True)
class ReviewPeriod:
    position: str
    days: int
    starts_days_ago: int
    set_on: Ago


REVIEW_PERIODS = (
    ReviewPeriod("DO-AHD", 15, 75, Ago(75, "09:00")),
    ReviewPeriod("DO-VAD", 30, 75, Ago(75, "09:15")),
    ReviewPeriod("DO-GNR", 30, 75, Ago(75, "09:30")),
)
# The batch job runs at this time every night (as the real scheduler will), creating a batch
# for each review period that has ended; the seed's last step runs it once more for today.
NIGHTLY_BATCH_JOB = "01:00"

# --- Sales ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Sale:
    """One transaction. Steps left out have not happened (yet): a sale with no buyer step is
    waiting for the buyer, and so on. `key` names sales that other events refer to."""

    seller: str
    buyer_business: str
    substance: str
    litres: int
    started: Ago | HoursAgo
    buyer: Step | None = None
    officer: Step | None = None
    superintendent: Step | None = None
    cancelled: Ago | None = None
    key: str = ""


SALES = (
    # 75 to 61 days ago (Ahmedabad's first review period).
    Sale("sanand_spirits", "bopal_bar", "WHISKY", 40, Ago(74),
         buyer=Step("CONFIRM", Ago(74, "15:00")), officer=Step("APPROVE", Ago(73, "11:00"))),
    Sale("sanand_spirits", "bavla_liquor", "VODKA", 120, Ago(72),
         buyer=Step("CONFIRM", Ago(72, "15:00")), officer=Step("APPROVE", Ago(71, "11:00"))),
    Sale("daskroi_beverages", "bopal_bar", "BEER", 80, Ago(70),
         buyer=Step("CONFIRM", Ago(70, "15:00")), officer=Step("APPROVE", Ago(69, "11:00"))),
    Sale("vadodara_distributors", "padra_permit_room", "WHISKY", 60, Ago(68),
         buyer=Step("CONFIRM", Ago(68, "15:00")), officer=Step("APPROVE", Ago(67, "11:00"))),
    Sale("sanand_spirits", "hotel_sabarmati", "WHISKY", 180, Ago(66), key="flagged",
         buyer=Step("CONFIRM", Ago(66, "15:00")), officer=Step("APPROVE", Ago(65, "11:00"))),
    Sale("sanand_spirits", "kanbha_traders", "WHISKY", 100, Ago(64),
         buyer=Step("CONFIRM", Ago(64, "15:00")),
         officer=Step("REJECT", Ago(63, "11:00"), "TRANSPORTER_INVALID",
                      "The vehicle at the check post was not the one on the permit.")),
    Sale("sanand_spirits", "sanand_retail", "WHISKY", 250, Ago(62),
         buyer=Step("CONFIRM", Ago(62, "15:00")), officer=Step("RECOMMEND", Ago(61, "11:00")),
         superintendent=Step("APPROVE", Ago(60, "12:00"))),
    # Elsewhere, 75 to 61 days ago.
    Sale("gandhinagar_wholesale", "infocity_hotel", "WHISKY", 60, Ago(73, "11:30"),
         buyer=Step("CONFIRM", Ago(73, "16:00")), officer=Step("APPROVE", Ago(72, "12:30"))),
    Sale("kalol_beer_depot", "infocity_hotel", "BEER", 100, Ago(71, "11:30"),
         buyer=Step("CONFIRM", Ago(71, "16:00")), officer=Step("APPROVE", Ago(70, "12:30"))),
    Sale("padra_wholesale", "padra_permit_room", "WHISKY", 50, Ago(69, "11:30"),
         buyer=Step("CONFIRM", Ago(69, "16:00")), officer=Step("APPROVE", Ago(68, "12:30"))),
    Sale("gandhinagar_wholesale", "kalol_wine_shop", "WINE", 150, Ago(67, "11:30"),
         buyer=Step("CONFIRM", Ago(67, "16:00")), officer=Step("APPROVE", Ago(66, "12:30"))),
    Sale("vadodara_distributors", "alkapuri_liquor", "WHISKY", 80, Ago(65, "11:30"),
         buyer=Step("CONFIRM", Ago(65, "16:00")), officer=Step("APPROVE", Ago(64, "12:30"))),
    Sale("kalol_beer_depot", "infocity_hotel", "BEER", 80, Ago(63, "11:30"),
         key="kalol_rejected_63",
         buyer=Step("REJECT", Ago(63, "16:00"), "QUANTITY_WRONG", "We ordered 50 L.")),
    # 60 to 46 days ago.
    Sale("sanand_spirits", "bopal_bar", "RUM", 20, Ago(59),
         buyer=Step("CONFIRM", Ago(59, "15:00")), officer=Step("APPROVE", Ago(58, "11:00"))),
    Sale("daskroi_beverages", "bopal_bar", "BEER", 60, Ago(57),
         buyer=Step("CONFIRM", Ago(57, "15:00")), officer=Step("APPROVE", Ago(56, "11:00"))),
    Sale("vadodara_distributors", "padra_permit_room", "RUM", 40, Ago(55),
         buyer=Step("CONFIRM", Ago(55, "15:00")), officer=Step("APPROVE", Ago(54, "11:00"))),
    Sale("sanand_spirits", "bopal_bar", "WHISKY", 30, Ago(53),
         buyer=Step("CONFIRM", Ago(53, "15:00")), officer=Step("APPROVE", Ago(52, "11:00"))),
    Sale("sanand_spirits", "bavla_liquor", "WHISKY", 200, Ago(51), cancelled=Ago(51, "16:00")),
    Sale("sanand_spirits", "hotel_sabarmati", "RUM", 25, Ago(49),
         buyer=Step("CONFIRM", Ago(49, "15:00")), officer=Step("APPROVE", Ago(48, "11:00"))),
    Sale("sanand_spirits", "sanand_retail", "VODKA", 60, Ago(47), key="rejected_47",
         buyer=Step("REJECT", Ago(47, "15:00"), "QUANTITY_WRONG", "We ordered 40 L, not 60 L.")),
    Sale("vadodara_distributors", "sanand_spirits", "WHISKY", 600, Ago(46),
         buyer=Step("CONFIRM", Ago(46, "15:00")), officer=Step("RECOMMEND", Ago(45, "11:00")),
         superintendent=Step("APPROVE", Ago(44, "12:00"))),
    # Elsewhere, 60 to 46 days ago. A Whisky licence of its own lets the Kalol shop buy Whisky.
    Sale("padra_wholesale", "alkapuri_liquor", "VODKA", 40, Ago(60, "11:30"),
         buyer=Step("CONFIRM", Ago(60, "16:00")), officer=Step("APPROVE", Ago(59, "12:30"))),
    Sale("gandhinagar_wholesale", "kalol_wine_shop", "WHISKY", 120, Ago(58, "11:30"),
         buyer=Step("CONFIRM", Ago(58, "16:00")), officer=Step("APPROVE", Ago(57, "12:30"))),
    Sale("daskroi_beverages", "kalol_beer_depot", "BEER", 1500, Ago(56, "11:30"),
         buyer=Step("CONFIRM", Ago(56, "16:00")), officer=Step("APPROVE", Ago(55, "12:30"))),
    Sale("gandhinagar_wholesale", "infocity_hotel", "RUM", 30, Ago(54, "11:30"),
         buyer=Step("CONFIRM", Ago(54, "16:00")), officer=Step("APPROVE", Ago(53, "12:30"))),
    Sale("padra_wholesale", "vadodara_distributors", "WHISKY", 400, Ago(52, "11:30"),
         buyer=Step("CONFIRM", Ago(52, "16:00")), officer=Step("RECOMMEND", Ago(51, "12:30")),
         superintendent=Step("APPROVE", Ago(50, "14:00"))),
    Sale("kalol_beer_depot", "infocity_hotel", "BEER", 60, Ago(50, "11:30"),
         buyer=Step("CONFIRM", Ago(50, "16:00")),
         officer=Step("REJECT", Ago(49, "12:30"), "TRANSPORTER_INVALID")),
    Sale("gandhinagar_wholesale", "kalol_wine_shop", "WHISKY", 250, Ago(48, "11:30"),
         buyer=Step("CONFIRM", Ago(48, "16:00")), officer=Step("RECOMMEND", Ago(47, "12:30")),
         superintendent=Step("APPROVE", Ago(46, "14:00"))),
    # 45 to 31 days ago.
    Sale("sanand_spirits", "bopal_bar", "VODKA", 20, Ago(43),
         buyer=Step("CONFIRM", Ago(43, "15:00")), officer=Step("APPROVE", Ago(42, "11:00"))),
    Sale("daskroi_beverages", "bopal_bar", "BEER", 50, Ago(41),
         buyer=Step("CONFIRM", Ago(41, "15:00")), officer=Step("APPROVE", Ago(40, "11:00"))),
    Sale("sanand_spirits", "kanbha_traders", "WHISKY", 90, Ago(39),
         buyer=Step("CONFIRM", Ago(39, "15:00")), officer=Step("APPROVE", Ago(38, "11:00"))),
    Sale("sanand_spirits", "bopal_bar", "WHISKY", 40, Ago(37),
         buyer=Step("CONFIRM", Ago(37, "15:00")), officer=Step("APPROVE", Ago(36, "11:00"))),
    Sale("sanand_spirits", "sanand_retail", "WHISKY", 240, Ago(35),
         buyer=Step("CONFIRM", Ago(35, "15:00")), officer=Step("RECOMMEND", Ago(34, "11:00")),
         superintendent=Step("REJECT", Ago(33, "12:00"), "OTHER",
                             "The shop's storage inspection is still pending.")),
    Sale("daskroi_beverages", "bopal_bar", "BEER", 70, Ago(33), key="rejected_33",
         buyer=Step("REJECT", Ago(33, "15:00"), "QUANTITY_WRONG", "We ordered 50 L.")),
    Sale("vadodara_distributors", "padra_permit_room", "VODKA", 30, Ago(32),
         buyer=Step("CONFIRM", Ago(32, "15:00")), officer=Step("APPROVE", Ago(31, "11:00"))),
    # Elsewhere, 45 to 31 days ago.
    Sale("padra_wholesale", "padra_permit_room", "RUM", 30, Ago(44, "11:30"),
         buyer=Step("CONFIRM", Ago(44, "16:00")), officer=Step("APPROVE", Ago(43, "12:30"))),
    Sale("vadodara_distributors", "alkapuri_liquor", "VODKA", 50, Ago(42, "11:30"),
         cancelled=Ago(42, "15:00")),
    Sale("gandhinagar_wholesale", "kalol_wine_shop", "WINE", 100, Ago(38, "11:30"),
         buyer=Step("CONFIRM", Ago(38, "16:00")), officer=Step("APPROVE", Ago(37, "12:30"))),
    Sale("gandhinagar_wholesale", "kalol_wine_shop", "WHISKY", 280, Ago(36, "11:30"),
         buyer=Step("CONFIRM", Ago(36, "16:00")), officer=Step("RECOMMEND", Ago(35, "12:30")),
         superintendent=Step("REJECT", Ago(34, "14:00"), "OTHER",
                             "The new godown has not been inspected yet.")),
    Sale("padra_wholesale", "alkapuri_liquor", "WHISKY", 60, Ago(34, "11:30"),
         key="padra_rejected_34",
         buyer=Step("REJECT", Ago(34, "16:00"), "NOT_ORDERED")),
    Sale("daskroi_beverages", "infocity_hotel", "BEER", 80, Ago(32, "11:30"),
         buyer=Step("CONFIRM", Ago(32, "16:00")), officer=Step("APPROVE", Ago(31, "12:30"))),
    # 30 to 16 days ago.
    Sale("sanand_spirits", "sanand_retail", "WHISKY", 240, Ago(29),
         buyer=Step("CONFIRM", Ago(29, "15:00")), officer=Step("RECOMMEND", Ago(28, "11:00")),
         superintendent=Step("APPROVE", Ago(27, "12:00"))),
    # The seller's 1st buyer rejection in the last 30 days.
    Sale("sanand_spirits", "bavla_liquor", "VODKA", 50, Ago(26), key="rejected_26",
         buyer=Step("REJECT", Ago(26, "15:00"), "NOT_ORDERED")),
    Sale("sanand_spirits", "hotel_sabarmati", "WHISKY", 60, Ago(24),
         buyer=Step("CONFIRM", Ago(24, "15:00")), officer=Step("APPROVE", Ago(23, "11:00"))),
    Sale("vadodara_distributors", "padra_permit_room", "WHISKY", 80, Ago(22),
         cancelled=Ago(22, "13:00")),
    Sale("daskroi_beverages", "bopal_bar", "BEER", 40, Ago(21),
         buyer=Step("CONFIRM", Ago(21, "15:00")),
         officer=Step("REJECT", Ago(20, "11:00"), "QUANTITY_MISMATCH",
                      "Only 32 L were found at the check post.")),
    Sale("sanand_spirits", "bopal_bar", "WHISKY", 30, Ago(19),
         buyer=Step("CONFIRM", Ago(19, "15:00")), officer=Step("APPROVE", Ago(18, "11:00"))),
    Sale("vadodara_distributors", "padra_permit_room", "WHISKY", 70, Ago(17),
         buyer=Step("CONFIRM", Ago(17, "15:00")), officer=Step("APPROVE", Ago(16, "11:00"))),
    # Elsewhere, 30 to 16 days ago. Beer above 2000 L needs the superintendent from day 38.
    Sale("daskroi_beverages", "kalol_beer_depot", "BEER", 2500, Ago(30, "11:30"),
         buyer=Step("CONFIRM", Ago(30, "16:00")), officer=Step("RECOMMEND", Ago(29, "12:30")),
         superintendent=Step("APPROVE", Ago(28, "14:00"))),
    Sale("gandhinagar_wholesale", "sector21_wines", "WINE", 50, Ago(27, "11:30"),
         cancelled=Ago(27, "13:00")),
    Sale("padra_wholesale", "vadodara_distributors", "VODKA", 200, Ago(25, "11:30"),
         buyer=Step("CONFIRM", Ago(25, "16:00")), officer=Step("APPROVE", Ago(24, "12:30"))),
    Sale("kalol_beer_depot", "infocity_hotel", "BEER", 70, Ago(23, "11:30"),
         buyer=Step("CONFIRM", Ago(23, "16:00")),
         officer=Step("REJECT", Ago(22, "12:30"), "QUANTITY_MISMATCH",
                      "Only 60 L were found at the check post.")),
    Sale("gandhinagar_wholesale", "infocity_hotel", "WHISKY", 100, Ago(21, "11:30"),
         buyer=Step("CONFIRM", Ago(21, "16:00")), officer=Step("APPROVE", Ago(20, "12:30"))),
    Sale("padra_wholesale", "alkapuri_liquor", "WHISKY", 90, Ago(19, "11:30"),
         buyer=Step("CONFIRM", Ago(19, "16:00")), officer=Step("APPROVE", Ago(18, "12:30"))),
    # 15 to 2 days ago.
    Sale("vadodara_distributors", "padra_permit_room", "RUM", 30, Ago(14),
         buyer=Step("CONFIRM", Ago(14, "15:00")),
         officer=Step("REJECT", Ago(13, "11:00"), "TRANSPORTER_INVALID")),
    # Over the buyer's Whisky limit: a stock-limit rejection, which raises no alert and does
    # not count against the seller.
    Sale("sanand_spirits", "bopal_bar", "WHISKY", 80, Ago(12),
         buyer=Step("REJECT", Ago(12, "15:00"), "STOCK_LIMIT")),
    Sale("sanand_spirits", "sanand_retail", "VODKA", 40, Ago(10),
         buyer=Step("CONFIRM", Ago(10, "15:00")), officer=Step("APPROVE", Ago(9, "11:00"))),
    # The seller's 2nd buyer rejection in the last 30 days.
    Sale("sanand_spirits", "hotel_sabarmati", "WHISKY", 60, Ago(9), key="rejected_9",
         buyer=Step("REJECT", Ago(9, "15:00"), "NOT_ORDERED", "No one here ordered this.")),
    Sale("daskroi_beverages", "bopal_bar", "BEER", 50, Ago(7),
         buyer=Step("CONFIRM", Ago(7, "15:00")), officer=Step("APPROVE", Ago(6, "11:00"))),
    Sale("vadodara_distributors", "padra_permit_room", "WHISKY", 50, Ago(6),
         buyer=Step("CONFIRM", Ago(6, "15:00")), officer=Step("APPROVE", Ago(5, "11:00"))),
    Sale("sanand_spirits", "bavla_liquor", "WHISKY", 120, Ago(5),
         buyer=Step("CONFIRM", Ago(5, "15:00")), officer=Step("APPROVE", Ago(4, "11:00"))),
    Sale("vadodara_distributors", "padra_permit_room", "VODKA", 25, Ago(4),
         buyer=Step("CONFIRM", Ago(3, "11:00"))),
    # Elsewhere, 15 to 2 days ago. The Gandhinagar officer's alert stays unacknowledged.
    Sale("gandhinagar_wholesale", "kalol_wine_shop", "WINE", 120, Ago(15, "11:30"),
         buyer=Step("CONFIRM", Ago(15, "16:00")), officer=Step("APPROVE", Ago(14, "12:30"))),
    Sale("kalol_beer_depot", "infocity_hotel", "BEER", 90, Ago(13, "11:30"),
         buyer=Step("CONFIRM", Ago(13, "16:00")), officer=Step("APPROVE", Ago(12, "12:30"))),
    Sale("padra_wholesale", "padra_permit_room", "VODKA", 40, Ago(11, "11:30"),
         buyer=Step("CONFIRM", Ago(11, "16:00")),
         officer=Step("REJECT", Ago(10, "12:30"), "TRANSPORTER_INVALID")),
    Sale("gandhinagar_wholesale", "infocity_hotel", "VODKA", 30, Ago(8, "11:30"),
         buyer=Step("REJECT", Ago(8, "16:00"), "NOT_ORDERED", "We stock no Vodka.")),
    Sale("padra_wholesale", "vadodara_distributors", "WHISKY", 300, Ago(6, "11:30"),
         buyer=Step("CONFIRM", Ago(6, "16:00")), officer=Step("RECOMMEND", Ago(5, "12:30")),
         superintendent=Step("APPROVE", Ago(4, "14:00"))),
    # Waiting today: the superintendent's final approval ...
    Sale("sanand_spirits", "sanand_retail", "WHISKY", 260, Ago(3),
         buyer=Step("CONFIRM", Ago(3, "15:00")), officer=Step("RECOMMEND", Ago(2, "11:00"))),
    # ... the Area Officer's decision ...
    Sale("sanand_spirits", "hotel_sabarmati", "WHISKY", 50, Ago(2),
         buyer=Step("CONFIRM", Ago(2, "15:00"))),
    Sale("sanand_spirits", "bavla_liquor", "VODKA", 80, HoursAgo(6),
         buyer=Step("CONFIRM", HoursAgo(5))),
    # ... and the buyer's: one over their Whisky limit (they can only reject it), one to
    # confirm, and one they did not order (the seller's 3rd rejection in 30 days, if rejected).
    Sale("sanand_spirits", "bopal_bar", "WHISKY", 90, HoursAgo(4)),
    Sale("sanand_spirits", "bopal_bar", "RUM", 24, HoursAgo(3)),
    Sale("sanand_spirits", "bopal_bar", "VODKA", 36, HoursAgo(2)),
    # Waiting elsewhere: Kalol's officer, Gandhinagar's superintendent and Padra's officer ...
    Sale("kalol_beer_depot", "daskroi_beverages", "BEER", 600, Ago(4, "11:30"),
         buyer=Step("CONFIRM", Ago(3, "16:00"))),
    Sale("gandhinagar_wholesale", "kalol_wine_shop", "WHISKY", 220, Ago(3, "11:30"),
         buyer=Step("CONFIRM", Ago(3, "16:00")), officer=Step("RECOMMEND", Ago(2, "12:30"))),
    Sale("padra_wholesale", "padra_permit_room", "WHISKY", 60, Ago(2, "11:30"),
         buyer=Step("CONFIRM", Ago(2, "16:00"))),
    # ... and buyers: two of them not signed up yet (they see these once they sign up).
    Sale("gandhinagar_wholesale", "kathwada_inn", "WHISKY", 40, HoursAgo(6)),
    Sale("daskroi_beverages", "bavla_beer_point", "BEER", 100, HoursAgo(5)),
    Sale("vadodara_distributors", "alkapuri_liquor", "VODKA", 30, HoursAgo(4)),
    Sale("kalol_beer_depot", "infocity_hotel", "BEER", 50, HoursAgo(3)),
)  # fmt: skip

# --- Batch reviews and alerts ----------------------------------------------------------------


@dataclass(frozen=True)
class Flag:
    sale: str
    reason: str
    comment: str
    when: Ago


@dataclass(frozen=True)
class BatchReview:
    """The superintendent flags items in the batch for the period starting
    `period_starts_days_ago`, then signs it off."""

    position: str
    period_starts_days_ago: int
    signed: Ago
    flags: tuple[Flag, ...] = ()


# Ahmedabad's three oldest batches are signed (the first with a flag); its batch for 30 to 16
# days ago stays open and due soon. Vadodara's first batch is left unsigned and is overdue.
# Gandhinagar's first batch is signed and its second is open.
BATCH_REVIEWS = (
    BatchReview(
        "DO-AHD",
        75,
        Ago(55, "16:00"),
        (
            Flag(
                "flagged",
                "QUANTITY_UNUSUAL",
                "180 L is high for one hotel permit room.",
                Ago(55, "15:00"),
            ),
        ),
    ),
    BatchReview("DO-AHD", 60, Ago(40, "16:00")),
    BatchReview("DO-AHD", 45, Ago(24, "16:00")),
    BatchReview("DO-GNR", 75, Ago(30, "16:00")),
)


@dataclass(frozen=True)
class Acknowledgement:
    """An officer acknowledges the alert a sale raised for their position."""

    sale: str
    position: str
    when: Ago
    note: str = ""
    kind: str = "BUYER_REJECTION"


# Left unacknowledged: the Superintendent's alert for the 26-days-ago rejection, and both
# alerts for the 9-days-ago rejection (so the Area Officer has one waiting); elsewhere, the
# Vadodara superintendent's for Padra's rejection and both for Gandhinagar's 8-days-ago one.
ACKNOWLEDGEMENTS = (
    Acknowledgement("rejected_47", "AO-SND", Ago(46, "12:00"), "Called the buyer; a typo."),
    Acknowledgement("rejected_47", "DO-AHD", Ago(45, "12:00")),
    Acknowledgement("flagged", "AO-SND", Ago(53, "12:00"), "Checked the hotel's register.",
                    kind="SUPERINTENDENT_FLAG"),
    Acknowledgement("rejected_33", "AO-DSK", Ago(32, "12:00"), "Seller corrected the quantity."),
    Acknowledgement("rejected_33", "DO-AHD", Ago(31, "12:00")),
    Acknowledgement("rejected_26", "AO-SND", Ago(25, "12:00"), "Asked the seller to explain."),
    Acknowledgement("kalol_rejected_63", "AO-KLL", Ago(62, "12:00"), "Seller fixed the order."),
    Acknowledgement("kalol_rejected_63", "DO-GNR", Ago(61, "12:00")),
    Acknowledgement("padra_rejected_34", "AO-PDR", Ago(33, "12:30"), "Order cancelled by phone."),
)  # fmt: skip

# --- Rule changes ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    by: str
    outcome: str
    when: Ago
    note: str = ""


@dataclass(frozen=True)
class Proposal:
    drafted_by: str
    kind: str
    payload: dict
    justification: str
    drafted: Ago
    decision: Decision | None = None
    withdrawn: Ago | None = None


PROPOSALS = (
    # Approved: drafted by the Licensing Authority, approved by Head Authority A.
    Proposal(
        "licensing_authority",
        "APPROVAL_THRESHOLD",
        {"substance_code": "BEER", "superintendent_above_qty": "2000"},
        "Large beer consignments should get a second look, as whisky ones do.",
        Ago(40, "11:00"),
        decision=Decision("head_authority_a", "APPROVE", Ago(38, "15:00"), "Agreed."),
    ),
    # Withdrawn by the superintendent who drafted it.
    Proposal(
        "superintendent",
        "RULE_VERSION",
        {
            "licence_type_code": "HOTEL",
            "class_code": "SPIRITS",
            "may_buy": True,
            "may_sell": False,
            "may_transport": False,
            "max_stock_qty": "500",
            "max_per_transaction_qty": "250",
            "validity_months": 12,
        },
        "Hotels in Ahmedabad ask for larger single deliveries before festivals.",
        Ago(16, "11:00"),
        withdrawn=Ago(15, "10:00"),
    ),
    # Pending: drafted by Head Authority B, for Head Authority A to decide in the demo.
    Proposal(
        "head_authority_b",
        "RULE_VERSION",
        {
            "licence_type_code": "RETAIL",
            "class_code": "SPIRITS",
            "may_buy": True,
            "may_sell": False,
            "may_transport": False,
            "max_stock_qty": "1500",
            "max_per_transaction_qty": "300",
            "validity_months": 12,
        },
        "Retail vendors in growing towns keep reaching the 1000 L stock limit.",
        Ago(2, "17:00"),
    ),
)
