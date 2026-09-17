"""Curated hygiene indicators and self-declared checklist items.

Plain data, typed and diffable, matching the Phase 2 ingredient seed.

ABOUT THE PLACEHOLDER DETECTOR
------------------------------
There is no purpose-trained hygiene dataset yet. The `cv_labels` below map
the *placeholder* provider's raw labels onto indicators:

  * For the ONNX/YOLO provider, these are COCO class names. YOLOv8n
    pretrained on COCO detects 80 everyday objects, **none of which are
    hygiene indicators**. Detecting a "cup" and calling it visible waste is a
    stand-in that gives the pipeline real detections with real confidences to
    score -- it is not a hygiene model, and its precision on a real stall is
    unknown and probably poor.
  * For the heuristic provider, these labels are the synthetic codes the
    OpenCV signals emit.

`cv_labels` is data rather than a hardcoded table in cv_client specifically
so that dropping in a trained model is a seed update, not a code change.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from app.models.enums import IndicatorCode, RiskLevel, ViewCategory

_V = ViewCategory


@dataclass(frozen=True)
class IndicatorSeed:
    code: IndicatorCode
    display_name: str
    description: str
    severity: RiskLevel
    #: view -> penalty points. A *missing* view means "does not apply here";
    #: an explicit 0 means "applies, but is expected and carries no penalty".
    view_penalties: Dict[str, int]
    cv_labels: List[str] = field(default_factory=list)


SEED_INDICATORS: List[IndicatorSeed] = [
    IndicatorSeed(
        code=IndicatorCode.VISIBLE_WASTE,
        display_name="Visible waste or litter",
        description=(
            "Loose wrappers, peels, or discarded packaging on or around the "
            "work surface."
        ),
        severity=RiskLevel.HIGH,
        view_penalties={
            # Waste in the waste area is a working bin -- expected, and
            # penalising it would punish a vendor for owning one.
            _V.PREP_AREA.value: 18,
            _V.STORAGE_AREA.value: 12,
            _V.OVERALL.value: 8,
            _V.WASTE_AREA.value: 0,
        },
        cv_labels=[
            # COCO stand-ins: small handheld objects that plausibly read as
            # discarded items.
            "bottle",
            "cup",
            "wine glass",
            "banana",
            "apple",
            "orange",
            "heuristic:waste_density",
        ],
    ),
    IndicatorSeed(
        code=IndicatorCode.UNCOVERED_FOOD,
        display_name="Uncovered food",
        description=(
            "Food or ingredients left open to dust, flies, and handling."
        ),
        severity=RiskLevel.HIGH,
        view_penalties={
            _V.PREP_AREA.value: 20,
            _V.STORAGE_AREA.value: 15,
            _V.OVERALL.value: 10,
        },
        cv_labels=[
            # The weakest mapping of the set: a bowl of food and an open bowl
            # of ingredients are indistinguishable to a COCO model, and a
            # covered container looks much the same as an uncovered one.
            "bowl",
            "sandwich",
            "pizza",
            "donut",
            "cake",
            "hot dog",
            "broccoli",
            "carrot",
            "heuristic:open_surface",
        ],
    ),
    IndicatorSeed(
        code=IndicatorCode.CLUTTERED_SURFACE,
        display_name="Cluttered work surface",
        description=(
            "Work surfaces crowded with objects, making cleaning difficult "
            "and hiding contamination."
        ),
        severity=RiskLevel.MODERATE,
        view_penalties={
            _V.PREP_AREA.value: 10,
            _V.STORAGE_AREA.value: 8,
            _V.OVERALL.value: 6,
        },
        cv_labels=[
            "dining table",
            "chair",
            "bench",
            "heuristic:edge_density",
        ],
    ),
    IndicatorSeed(
        code=IndicatorCode.DIRTY_UTENSILS,
        display_name="Dirty or wet-stored utensils",
        description=(
            "Utensils left unwashed or stored wet, which supports bacterial "
            "growth."
        ),
        severity=RiskLevel.HIGH,
        view_penalties={
            _V.PREP_AREA.value: 16,
            _V.STORAGE_AREA.value: 10,
            _V.OVERALL.value: 6,
        },
        cv_labels=[
            # COCO does include these.
            "fork",
            "knife",
            "spoon",
            "heuristic:utensil_cluster",
        ],
    ),
    IndicatorSeed(
        code=IndicatorCode.STAGNANT_WATER,
        display_name="Standing water",
        description=(
            "Pooled water on the floor or surfaces, a breeding site for "
            "mosquitoes and a slip hazard."
        ),
        severity=RiskLevel.HIGH,
        view_penalties={
            _V.PREP_AREA.value: 14,
            _V.STORAGE_AREA.value: 10,
            _V.OVERALL.value: 8,
            _V.WASTE_AREA.value: 6,
        },
        # No COCO class for water pooling; heuristic-only today.
        cv_labels=["heuristic:standing_water"],
    ),
    IndicatorSeed(
        code=IndicatorCode.PEST_EVIDENCE,
        display_name="Signs of pests or stray animals",
        description=(
            "Animals, droppings, or other evidence of pest activity near "
            "food handling areas."
        ),
        severity=RiskLevel.HIGH,
        view_penalties={
            _V.PREP_AREA.value: 25,
            _V.STORAGE_AREA.value: 20,
            _V.OVERALL.value: 15,
            _V.WASTE_AREA.value: 10,
        },
        cv_labels=[
            # COCO has these animal classes. Detecting a stray dog near a
            # stall is the single most plausible COCO-derived signal in this
            # whole table.
            "bird",
            "cat",
            "dog",
            "heuristic:pest_blob",
        ],
    ),
    IndicatorSeed(
        code=IndicatorCode.OPEN_DRAIN,
        display_name="Open drain or leaking pipe",
        description=(
            "Uncovered drains or leaks near the stall that can splash "
            "contaminated water onto food or surfaces."
        ),
        severity=RiskLevel.MODERATE,
        view_penalties={
            _V.PREP_AREA.value: 12,
            _V.STORAGE_AREA.value: 8,
            _V.OVERALL.value: 10,
            _V.WASTE_AREA.value: 12,
        },
        # No COCO class; heuristic-only today.
        cv_labels=["heuristic:linear_dark_region"],
    ),
]


@dataclass(frozen=True)
class ChecklistItemSeed:
    code: str
    label: str
    help_text: str


#: Self-declared compliance items. Worth only 30% of the score by design --
#: these are unverified statements, and a vendor must not be able to lift a
#: failing visual score just by ticking boxes.
SEED_CHECKLIST_ITEMS: List[ChecklistItemSeed] = [
    ChecklistItemSeed(
        code="covered_waste_bin",
        label="I have a covered waste bin inside the stall",
        help_text="A bin with a lid, emptied regularly.",
    ),
    ChecklistItemSeed(
        code="clean_water",
        label="Clean water is available for washing",
        help_text="Running water or a stored supply kept clean.",
    ),
    ChecklistItemSeed(
        code="no_hand_contact",
        label="Food is handled with tongs, gloves, or washed hands",
        help_text="Not touched directly with bare hands.",
    ),
    ChecklistItemSeed(
        code="utensils_covered",
        label="Utensils are washed and stored covered",
        help_text="Not left out in the open or stored wet.",
    ),
    ChecklistItemSeed(
        code="food_off_ground",
        label="Food and ingredients are stored off the ground",
        help_text="On a table, rack, or shelf, not on the floor.",
    ),
    ChecklistItemSeed(
        code="no_stray_animals",
        label="No stray animals come near the stall",
        help_text="Dogs, cats, and birds kept away from food.",
    ),
]


#: Checklist item code -> whether answering "yes" is good. Every item is
#: currently phrased positively, so all are True; the map exists so a
#: future negatively-phrased item ("I reuse frying oil") scores correctly
#: instead of being silently inverted.
CHECKLIST_POSITIVE = {item.code: True for item in SEED_CHECKLIST_ITEMS}
