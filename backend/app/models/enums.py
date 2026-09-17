"""Shared enums for the food-safety domain.

Kept in one module so models, schemas, services, and the seed data all agree
on the exact string values. These values are persisted, so changing one is a
data migration, not a rename.
"""

import enum


class UserRole(str, enum.Enum):
    VENDOR = "vendor"
    REVIEWER = "reviewer"
    CONSUMER = "consumer"
    ADMIN = "admin"

    @classmethod
    def self_assignable(cls) -> set["UserRole"]:
        """Roles a member of the public may pick at registration.

        REVIEWER and ADMIN are deliberately excluded: allowing them through
        the public registration endpoint would let anyone grant themselves
        dashboard access. Privileged accounts must be provisioned
        out-of-band.
        """
        return {cls.VENDOR, cls.CONSUMER}


class ScanStatus(str, enum.Enum):
    """The five product-scan outcomes.

    Note these are NOT ordered by severity; the pipeline picks one via an
    explicit precedence table in services/products/status_engine.py.
    """

    SUITABLE = "Suitable"
    POTENTIAL_CONCERN = "Potential concern"
    APPLICATION_MISMATCH = "Application mismatch"
    INSUFFICIENT_INFORMATION = "Insufficient information"
    NEEDS_REVIEW = "Needs review"


class IngredientCategory(str, enum.Enum):
    FAT_OIL = "Fat/Oil"
    PRESERVATIVE = "Preservative"
    ARTIFICIAL_COLOUR = "Artificial colour"
    COLOUR = "Colour"
    FLAVOUR_ENHANCER = "Flavour enhancer"
    SWEETENER = "Sweetener"
    ANTIOXIDANT = "Antioxidant"
    EMULSIFIER = "Emulsifier"
    ACIDITY_REGULATOR = "Acidity regulator"
    THICKENER = "Thickener"
    CEREAL = "Cereal"
    MINERAL = "Mineral"
    DAIRY = "Dairy"
    SPICE = "Spice"
    OTHER = "Other"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"

    @property
    def weight(self) -> float:
        """Contribution to the rule-strength term of the confidence score.

        A triggered high-risk rule is treated as *stronger evidence* than a
        triggered low-risk one, because the rule is more specific and the
        match matters more.
        """
        return {RiskLevel.LOW: 0.5, RiskLevel.MODERATE: 0.7, RiskLevel.HIGH: 0.9}[self]


class RuleType(str, enum.Enum):
    """How an ingredient rule is evaluated.

    PRESENCE              -- any occurrence triggers.
    THRESHOLD             -- compares the parsed percentage against
                             conditions["max_pct"].
    CATEGORY_RESTRICTION  -- ingredient is permitted only within
                             conditions["allowed_categories"]; compared
                             against the stall's food_category. This is what
                             produces the "Application mismatch" status.
    """

    PRESENCE = "presence"
    THRESHOLD = "threshold"
    CATEGORY_RESTRICTION = "category_restriction"


class MatchMethod(str, enum.Enum):
    """How an OCR token was resolved to a knowledge-base ingredient.

    Ordered strongest to weakest; the method feeds match confidence.
    """

    EXACT = "exact"          # canonical name matched verbatim
    E_NUMBER = "e_number"    # INS/E number, e.g. "INS 211" -> E211
    ALIAS = "alias"          # curated synonym or common trade name
    FUZZY = "fuzzy"          # OCR typo recovered by edit-distance


class AliasType(str, enum.Enum):
    COMMON_NAME = "common_name"
    E_NUMBER = "e_number"
    INS_NUMBER = "ins_number"
    OCR_VARIANT = "ocr_variant"


class ViewCategory(str, enum.Enum):
    """The four stall views a complete hygiene check requires.

    All four must be present before indicator detection runs -- an assessment
    from a partial set would produce a score that looks authoritative and is
    not.
    """

    OVERALL = "overall"
    PREP_AREA = "prep_area"
    STORAGE_AREA = "storage_area"
    WASTE_AREA = "waste_area"

    @property
    def prompt(self) -> str:
        """Vendor-facing instruction for the capture step."""
        return {
            ViewCategory.OVERALL: "Now photograph the whole stall",
            ViewCategory.PREP_AREA: "Now photograph the preparation area",
            ViewCategory.STORAGE_AREA: "Now photograph the storage area",
            ViewCategory.WASTE_AREA: "Now photograph the waste area",
        }[self]

    @property
    def hint(self) -> str:
        """One line telling the vendor what belongs in this shot."""
        return {
            ViewCategory.OVERALL: "Stand back so the whole stall is in frame",
            ViewCategory.PREP_AREA: "Where food is cut, cooked, or plated",
            ViewCategory.STORAGE_AREA: "Where ingredients and containers are kept",
            ViewCategory.WASTE_AREA: "Bins, dustbins, and any drain nearby",
        }[self]

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


#: Order the guided capture flow presents the views in, and the canonical
#: order for coverage checks. Broad first, so the vendor has context.
REQUIRED_VIEWS: tuple[ViewCategory, ...] = (
    ViewCategory.OVERALL,
    ViewCategory.PREP_AREA,
    ViewCategory.STORAGE_AREA,
    ViewCategory.WASTE_AREA,
)


class CheckStatus(str, enum.Enum):
    """Lifecycle of a hygiene check.

    A check is created as DRAFT when the vendor opens the capture flow, moves
    to AWAITING_VIEWS once the first image lands, and only becomes SCORED
    when all four views are present and the pipeline has run.
    """

    DRAFT = "draft"
    AWAITING_VIEWS = "awaiting_views"
    SCORED = "scored"
    FAILED = "failed"


class IndicatorCode(str, enum.Enum):
    """Visible hygiene indicators the CV layer looks for.

    These are the *placeholder* taxonomy. See integrations/cv_client.py for
    how they are matched today and what changes when a purpose-trained model
    replaces the stand-in.
    """

    VISIBLE_WASTE = "visible_waste"
    UNCOVERED_FOOD = "uncovered_food"
    CLUTTERED_SURFACE = "cluttered_surface"
    DIRTY_UTENSILS = "dirty_utensils"
    STAGNANT_WATER = "stagnant_water"
    PEST_EVIDENCE = "pest_evidence"
    OPEN_DRAIN = "open_drain"


class DetectionSource(str, enum.Enum):
    """Which provider produced a detection.

    Recorded on every detection so a verdict can be traced back to the
    method that produced it -- the placeholder COCO mapping and the
    heuristic path have very different reliability.
    """

    HEURISTIC = "heuristic"
    ONNX_YOLO = "onnx_yolo"


class FlagStatus(str, enum.Enum):
    """Lifecycle of a reviewer flag.

    OPEN flags are what the dashboard surfaces by default. RESOLVED flags are
    kept rather than deleted so the history answers "was this looked at, by
    whom, and when" -- which is the whole point of recording who raised it.
    """

    OPEN = "open"
    RESOLVED = "resolved"


class ReviewSort(str, enum.Enum):
    """Sort keys for the reviewer vendors table.

    Constrained to a fixed set rather than accepting a column name: the sort
    key reaches an ORDER BY, and an unvalidated string there is an injection
    surface and a way to sort by a column that is not exposed.
    """

    STALL_NAME = "stall_name"
    HYGIENE = "hygiene"
    LAST_SCAN = "last_scan"
    LAST_ACTIVITY = "last_activity"
    CREATED_AT = "created_at"
