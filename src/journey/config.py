"""Central configuration: paths, scoring weights and the mission taxonomy.

Everything a marketer might want to tune lives here, not inside the logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
CHARTS = OUTPUTS / "charts"

# Portfolio palette (devinder-kaur.vercel.app)
PALETTE = {
    "navy": "#2F4156",
    "teal": "#567C8D",
    "sky": "#C8D9E6",
    "beige": "#F5EFEB",
    "white": "#FFFFFF",
    "muted": "#8A9AAB",
}

# How much each behaviour tells us about intent.
EVENT_WEIGHTS = {"view": 1.0, "cart": 3.0, "purchase": 5.0}


@dataclass(frozen=True)
class Mission:
    """A life event or project that shows up as a *pattern* across categories.

    A single sofa view is noise. Sofa + bed + fridge + drill inside a few weeks
    is somebody furnishing a new home. `needs` are category_code prefixes from
    the REES46 taxonomy; the order of `needs` is the typical journey order and is
    only used for display, never for scoring.
    """

    key: str
    name: str
    signal: str  # one-line description of what the pattern means
    needs: tuple[str, ...]
    min_needs: int = 2  # distinct needs required before we call it a mission


MISSIONS: tuple[Mission, ...] = (
    Mission(
        key="new_home",
        name="Setting up a new home",
        signal="Furniture across rooms + large appliances + tools in a short window",
        needs=(
            "furniture.living_room",
            "furniture.bedroom",
            "furniture.kitchen",
            "furniture.bathroom",
            "furniture.universal",
            "appliances.kitchen.refrigerators",
            "appliances.kitchen.washer",
            "appliances.kitchen.oven",
            "appliances.kitchen.hood",
            "appliances.environment",
            "construction.tools",
        ),
        min_needs=3,
    ),
    Mission(
        key="growing_family",
        name="Preparing for a baby / growing family",
        signal="Strollers and car seats first, then nursery furniture, toys and safety",
        needs=(
            "kids.carriage",
            "kids.toys",
            "kids.dolls",
            "kids.skates",
            "furniture.bedroom.cradle",
            "appliances.environment.air_heater",
            "appliances.kitchen.blender",
        ),
    ),
    Mission(
        key="home_office",
        name="Building a home office",
        signal="Laptop or desktop, then monitor, peripherals, chair and audio",
        needs=(
            "computers.notebook",
            "computers.desktop",
            "computers.peripherals",
            "computers.components",
            "furniture.office",
            "electronics.audio.headphone",
            "stationery",
        ),
    ),
    Mission(
        key="kitchen_upgrade",
        name="Upgrading the kitchen",
        signal="Several small kitchen appliances researched together",
        needs=(
            "appliances.kitchen.microwave",
            "appliances.kitchen.kettle",
            "appliances.kitchen.coffee_machine",
            "appliances.kitchen.toster",
            "appliances.kitchen.mixer",
            "appliances.kitchen.juicer",
            "appliances.kitchen.meat_grinder",
        ),
    ),
    Mission(
        key="active_lifestyle",
        name="Starting an active lifestyle",
        signal="Bike or trainer, then wearables, shoes and outdoor kit",
        needs=(
            "sport.bicycle",
            "sport.trainer",
            "sport.tennis",
            "electronics.clocks",
            "apparel.shoes",
            "apparel.trousers",
            "accessories.bag",
        ),
    ),
    Mission(
        key="entertainment",
        name="Building a home entertainment setup",
        signal="TV first, then sound, consoles and accessories",
        needs=(
            "electronics.video.tv",
            "electronics.audio.acoustic",
            "electronics.audio.subwoofer",
            "electronics.video.projector",
            "electronics.audio.music_tools",
            "furniture.living_room.cabinet",
        ),
    ),
)


@dataclass
class PipelineConfig:
    # Temporal split. REES46 Oct 2019 = history, Nov 2019 = what happened next.
    cutoff: str = "2019-11-01"
    horizon_days: int = 30
    # Sampling: the full Oct file is ~42M rows. Keep 1 in N users by hash.
    user_sample_mod: int = 20
    # Stage rules
    research_sessions: int = 4  # sessions on a mission before "Researching"
    open_cart_days: int = 14  # a cart older than this is abandoned, not "ready to buy"
    gone_quiet_days: int = 14  # no mission activity for this long = "Gone quiet"
    complete_needs: int = 3  # purchased needs before "Mission complete"
    # Mission detection
    mission_min_score: float = 6.0
    recency_half_life_days: float = 14.0
    # Recommendation
    top_k: int = 5
    mission_boost: float = 1.5  # multiplier for candidates inside an active mission
    # Ad suppression ("don't show the same ad again")
    purchase_cooldown_days: int = 60
    fatigue_views: int = 5  # product views with no cart...
    fatigue_sessions: int = 3  # ...spread across this many sessions = stop retargeting it
    files: list[str] = field(default_factory=lambda: ["2019-Oct.csv", "2019-Nov.csv"])
