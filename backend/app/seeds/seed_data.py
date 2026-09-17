"""Curated ingredients for Indian packaged and street food.

Deliberately a module of plain data rather than a JSON/YAML file: the values
are typed (enums are checked at import), the file is diffable, and adding an
ingredient is a code review away from being live.

The seed is applied idempotently by `python -m app.seeds.ingredients_seed`
-- see that module's docstring for the upsert semantics.
"""

from dataclasses import dataclass, field
from typing import List

from app.models.enums import (
    AliasType,
    IngredientCategory,
    RiskLevel,
    RuleType,
    ScanStatus,
)


@dataclass(frozen=True)
class SynonymSeed:
    alias: str
    alias_type: AliasType = AliasType.COMMON_NAME


@dataclass(frozen=True)
class RecommendationSeed:
    title: str
    body: str
    priority: int = 100


@dataclass(frozen=True)
class RuleSeed:
    rule_type: RuleType
    status: ScanStatus
    template: str
    """English explanation template. Available placeholders:
    {ingredient} {category} {allowed} {max_pct} {percent}.
    Rendered by services/products/explanation.py."""

    conditions: dict = field(default_factory=dict)


@dataclass(frozen=True)
class IngredientSeed:
    canonical_name: str
    category: IngredientCategory
    risk: RiskLevel
    description: str
    synonyms: List[SynonymSeed]
    # None means "no rule" -> the ingredient can never trigger a concern, so
    # a label containing only rule-free ingredients produces "Suitable".
    rule: RuleSeed | None = None
    recommendations: List[RecommendationSeed] = field(default_factory=list)


def _syn(alias: str, alias_type: AliasType = AliasType.COMMON_NAME) -> SynonymSeed:
    return SynonymSeed(alias=alias, alias_type=alias_type)


def _e(number: str) -> SynonymSeed:
    """E-number, e.g. "E211"."""
    return SynonymSeed(alias=number, alias_type=AliasType.E_NUMBER)


def _ins(number: str) -> SynonymSeed:
    """INS number as printed on Indian labels, e.g. "INS 211"."""
    return SynonymSeed(alias=number, alias_type=AliasType.INS_NUMBER)


_BEVERAGES_AND_SWEETS = ["Beverages", "Sweets & Confectionery", "Snacks"]


SEED_INGREDIENTS: List[IngredientSeed] = [
    # ------------------------------------------------------------------
    # Fats and oils
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="Palm Oil",
        category=IngredientCategory.FAT_OIL,
        risk=RiskLevel.HIGH,
        description="A high-saturation vegetable oil widely used for frying.",
        synonyms=[
            _syn("palm oil"),
            _syn("refined palm oil"),
            _syn("edible palm oil"),
            _syn("palmoil", AliasType.OCR_VARIANT),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is high in saturated fat. Repeated reheating for "
                "deep frying raises the level of trans fats, which FSSAI "
                "advises limiting. If you reuse frying oil, discard it once it "
                "darkens or smokes."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Limit oil reuse",
                body=(
                    "Do not top up a frying pan with fresh oil indefinitely. "
                    "Discard oil when it darkens, foams, or smells rancid."
                ),
                priority=20,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Palmolein Oil",
        category=IngredientCategory.FAT_OIL,
        risk=RiskLevel.HIGH,
        description="A liquid fraction of palm oil, common in Indian frying.",
        synonyms=[_syn("palmolein"), _syn("palmolein oil"), _syn("refined palmolein")],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a refined palm fraction high in saturated fat. "
                "Store it away from sunlight and do not reuse it for more than "
                "a few frying cycles."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Store oil out of sunlight",
                body="Keep sealed and away from direct sun to slow oxidation.",
                priority=60,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Hydrogenated Vegetable Oil",
        category=IngredientCategory.FAT_OIL,
        risk=RiskLevel.HIGH,
        description="Vanaspati; partially hydrogenated fat containing trans fats.",
        synonyms=[
            _syn("hydrogenated vegetable oil"),
            _syn("vanaspati"),
            _syn("partially hydrogenated vegetable oil"),
            _syn("hydrogenated fat"),
            _syn("shortening"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} (vanaspati) is a partially hydrogenated fat and a "
                "major source of trans fats. FSSAI requires trans fat in "
                "edible oils to stay under 2% by weight, and WHO recommends "
                "avoiding industrial trans fats entirely."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Switch away from vanaspati",
                body=(
                    "Replace with a non-hydrogenated oil or a blend, and check "
                    "the label for the words 'hydrogenated' or 'partially "
                    "hydrogenated'."
                ),
                priority=10,
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # Flavour enhancers
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="Monosodium Glutamate",
        category=IngredientCategory.FLAVOUR_ENHANCER,
        risk=RiskLevel.MODERATE,
        description="MSG; the flavour enhancer sold as Ajinomoto.",
        synonyms=[
            _syn("monosodium glutamate"),
            _syn("msg"),
            _syn("ajinomoto"),
            _syn("flavour enhancer 621"),
            _syn("flavor enhancer"),
            _e("E621"),
            _ins("INS 621"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} (MSG / Ajinomoto) is a flavour enhancer. It is "
                "permitted in India, but some customers avoid it and it can be "
                "a hidden source of sodium. Because you are selling as "
                "{category}, tell customers it is present."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Declare MSG to customers",
                body=(
                    "Some customers specifically avoid MSG. A small sign or a "
                    "spoken note avoids complaints."
                ),
                priority=50,
            ),
            RecommendationSeed(
                title="Watch total sodium",
                body="MSG adds sodium on top of salt. Reduce added salt if you keep using it.",
                priority=70,
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # Preservatives
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="Sodium Benzoate",
        category=IngredientCategory.PRESERVATIVE,
        risk=RiskLevel.MODERATE,
        description="A common preservative, permitted only in certain food categories.",
        synonyms=[
            _syn("sodium benzoate"),
            _syn("benzoate of soda"),
            _syn("sodium salt of benzoic acid"),
            _e("E211"),
            _ins("INS 211"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.CATEGORY_RESTRICTION,
            conditions={"allowed_categories": _BEVERAGES_AND_SWEETS},
            status=ScanStatus.APPLICATION_MISMATCH,
            template=(
                "{ingredient} is a preservative permitted by FSSAI only in "
                "specified food categories. This label was scanned for a stall "
                "selling {category}, which is not among the permitted uses."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Check the permitted category",
                body=(
                    "Confirm with your supplier that this product is intended "
                    "for what you sell, and keep the invoice in case an officer "
                    "asks."
                ),
                priority=15,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Potassium Sorbate",
        category=IngredientCategory.PRESERVATIVE,
        risk=RiskLevel.MODERATE,
        description="Preservative often paired with sodium benzoate.",
        synonyms=[
            _syn("potassium sorbate"),
            _syn("sorbate"),
            _e("E202"),
            _ins("INS 202"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.THRESHOLD,
            conditions={"max_pct": 0.2},
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a preservative used here at {percent}, against "
                "a guideline maximum of {max_pct} for this type of product. "
                "Above the limit it should not be sold."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Confirm the permitted level",
                body="Ask your supplier for the permitted usage level for this product type.",
                priority=40,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Sodium Nitrite",
        category=IngredientCategory.PRESERVATIVE,
        risk=RiskLevel.HIGH,
        description="Curing salt permitted only in processed meat.",
        synonyms=[
            _syn("sodium nitrite"),
            _syn("nitrite"),
            _syn("curing salt"),
            _e("E250"),
            _ins("INS 250"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.CATEGORY_RESTRICTION,
            conditions={"allowed_categories": ["Meat & Poultry"]},
            status=ScanStatus.APPLICATION_MISMATCH,
            template=(
                "{ingredient} is a curing salt permitted only in processed meat "
                "and poultry. This stall sells {category}, so this product is "
                "not intended for use here."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Do not use curing salts outside meat",
                body=(
                    "Nitrite is strictly limited to cured meat products under "
                    "FSSAI rules. Using it elsewhere is a serious violation."
                ),
                priority=5,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Calcium Propionate",
        category=IngredientCategory.PRESERVATIVE,
        risk=RiskLevel.LOW,
        description="Mould inhibitor used in bread and bakery products.",
        synonyms=[
            _syn("calcium propionate"),
            _syn("propionate"),
            _e("E282"),
            _ins("INS 282"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.THRESHOLD,
            conditions={"max_pct": 0.3},
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a mould inhibitor commonly used in bread. It is "
                "listed here at {percent} against a guideline maximum of "
                "{max_pct}."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Fine for most bakery use",
                body="No action needed unless the declared level exceeds the guideline.",
                priority=90,
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # Colours
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="Tartrazine",
        category=IngredientCategory.ARTIFICIAL_COLOUR,
        risk=RiskLevel.HIGH,
        description="Synthetic yellow azo dye, permitted only in set categories.",
        synonyms=[
            _syn("tartrazine"),
            _syn("yellow 5"),
            _syn("fd&c yellow no. 5"),
            _syn("ci 19140"),
            _e("E102"),
            _ins("INS 102"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.CATEGORY_RESTRICTION,
            conditions={"allowed_categories": _BEVERAGES_AND_SWEETS},
            status=ScanStatus.APPLICATION_MISMATCH,
            template=(
                "{ingredient} is a synthetic yellow colour permitted only in "
                "specified food categories. It was found in a product used by a "
                "stall selling {category}."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Synthetic colours are category-restricted",
                body=(
                    "If this product is not intended for your food category, "
                    "switch to a supplier product formulated for it."
                ),
                priority=10,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Sunset Yellow FCF",
        category=IngredientCategory.ARTIFICIAL_COLOUR,
        risk=RiskLevel.HIGH,
        description="Synthetic orange azo dye, category-restricted.",
        synonyms=[
            _syn("sunset yellow"),
            _syn("sunset yellow fcf"),
            _syn("yellow 6"),
            _syn("orange yellow s"),
            _e("E110"),
            _ins("INS 110"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.CATEGORY_RESTRICTION,
            conditions={"allowed_categories": _BEVERAGES_AND_SWEETS},
            status=ScanStatus.APPLICATION_MISMATCH,
            template=(
                "{ingredient} is a synthetic colour permitted only in specified "
                "categories. This stall sells {category}, which is outside the "
                "permitted list."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Check permitted categories",
                body="Synthetic colours cannot be used freely across all food types.",
                priority=10,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Carmoisine",
        category=IngredientCategory.ARTIFICIAL_COLOUR,
        risk=RiskLevel.HIGH,
        description="Synthetic red azo dye used in sweets and beverages.",
        synonyms=[
            _syn("carmoisine"),
            _syn("azorubine"),
            # NOT "red 3" -- that is FD&C Red No. 3 (erythrosine). Carmoisine
            # is Food Red 3, and the two collide on the bare "red 3" form.
            _syn("food red 3"),
            _syn("ci 14720"),
            _e("E122"),
            _ins("INS 122"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a synthetic red colour. Synthetic colours are a "
                "common cause of sensitivity in children, and FSSAI requires "
                "declaring them on the label."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Declare synthetic colour",
                body="Ensure the colour is declared on your menu or board if you add it.",
                priority=45,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Allura Red AC",
        category=IngredientCategory.ARTIFICIAL_COLOUR,
        risk=RiskLevel.HIGH,
        description="Synthetic red dye, restricted in several countries.",
        synonyms=[
            _syn("allura red"),
            _syn("allura red ac"),
            _syn("red 40"),
            _e("E129"),
            _ins("INS 129"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a synthetic azo dye. It is restricted in some "
                "countries and should be declared where it is used."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Prefer a natural colour where possible",
                body="Natural alternatives exist for most applications in street food.",
                priority=65,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Brilliant Blue FCF",
        category=IngredientCategory.ARTIFICIAL_COLOUR,
        risk=RiskLevel.MODERATE,
        description="Synthetic blue dye used in sweets and syrups.",
        synonyms=[
            _syn("brilliant blue"),
            _syn("brilliant blue fcf"),
            _syn("blue 1"),
            _e("E133"),
            _ins("INS 133"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a synthetic blue colour. Declare it where it is "
                "used so customers who avoid synthetic colours can choose."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Declare synthetic colour",
                body="Label or announce it where customers can see.",
                priority=75,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Erythrosine",
        category=IngredientCategory.ARTIFICIAL_COLOUR,
        risk=RiskLevel.HIGH,
        description="Synthetic cherry-red dye, restricted in many markets.",
        synonyms=[
            _syn("erythrosine"),
            _syn("red 3"),
            _syn("fd&c red no. 3"),
            _syn("acid red 51"),
            _e("E127"),
            _ins("INS 127"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a synthetic colour with restricted use in "
                "several countries. It should not be used without checking the "
                "permitted category."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Check permitted use",
                body="Confirm the permitted category with your supplier before use.",
                priority=35,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Caramel Colour",
        category=IngredientCategory.COLOUR,
        risk=RiskLevel.LOW,
        description="Brown colouring used in colas, sauces, and sweets.",
        synonyms=[
            _syn("caramel colour"),
            _syn("caramel color"),
            _syn("caramel"),
            _e("E150"),
            _ins("INS 150"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a brown colouring. It is generally regarded as "
                "low risk, but it is still an added colour rather than a "
                "natural ingredient."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Low concern",
                body="No action needed unless you are avoiding all added colours.",
                priority=95,
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # Sweeteners
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="Aspartame",
        category=IngredientCategory.SWEETENER,
        risk=RiskLevel.MODERATE,
        description="Artificial sweetener, unsuitable for phenylketonurics.",
        synonyms=[
            _syn("aspartame"),
            _syn("nutrasweet"),
            _syn("equal"),
            _e("E951"),
            _ins("INS 951"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is an artificial sweetener. Products containing it "
                "must carry a warning for people with phenylketonuria (PKU)."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Check for the PKU warning",
                body=(
                    "If you sell this product directly, keep the package so the "
                    "required phenylketonuria warning stays visible."
                ),
                priority=55,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Saccharin",
        category=IngredientCategory.SWEETENER,
        risk=RiskLevel.MODERATE,
        description="Artificial sweetener with a permitted maximum level.",
        synonyms=[
            _syn("saccharin"),
            _syn("sodium saccharin"),
            _syn("saccharin sodium"),
            _e("E954"),
            _ins("INS 954"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is an artificial sweetener with a permitted "
                "maximum level that varies by food category. It should not be "
                "used in food meant for infants."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Not for infant food",
                body="Never use artificial sweeteners in anything sold for infants.",
                priority=25,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Sucralose",
        category=IngredientCategory.SWEETENER,
        risk=RiskLevel.LOW,
        description="Artificial sweetener, heat-stable, common in drinks.",
        synonyms=[_syn("sucralose"), _e("E955"), _ins("INS 955")],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is an artificial sweetener. Low risk at normal "
                "levels, but it is still an added sweetener rather than sugar."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Low concern",
                body="Declare it for customers who avoid artificial sweeteners.",
                priority=90,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="High Fructose Corn Syrup",
        category=IngredientCategory.SWEETENER,
        risk=RiskLevel.MODERATE,
        description="Liquid sweetener widely used in packaged drinks and sauces.",
        synonyms=[
            _syn("high fructose corn syrup"),
            _syn("hfcs"),
            _syn("fructose syrup"),
            _syn("glucose fructose syrup"),
            _syn("corn syrup"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a liquid sweetener. It raises the total sugar "
                "content without adding any nutritional value."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Watch added sugar",
                body="Cut back other sugars if you already use a sweetened sauce or drink.",
                priority=70,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Refined Sugar",
        category=IngredientCategory.SWEETENER,
        risk=RiskLevel.LOW,
        description="White sugar; a common ingredient in street food condiments.",
        synonyms=[
            _syn("refined sugar"),
            _syn("sugar"),
            _syn("white sugar"),
            _syn("sucrose"),
            _syn("cane sugar"),
            _syn("चीनी"),
            _syn("साखर"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.THRESHOLD,
            conditions={"max_pct": 15.0},
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is listed at {percent}, above the {max_pct} "
                "guideline for this type of product. High sugar content is a "
                "labelling and health concern."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Reduce added sugar",
                body="Consider a lower-sugar recipe or a smaller declared portion.",
                priority=80,
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # Mineral and cereal
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="Iodised Salt",
        category=IngredientCategory.MINERAL,
        risk=RiskLevel.LOW,
        description="Table salt with added iodine.",
        synonyms=[_syn("iodised salt"), _syn("iodized salt"), _syn("salt"), _syn("common salt"), _syn("नमक"), _syn("मीठ")],
        rule=RuleSeed(
            rule_type=RuleType.THRESHOLD,
            conditions={"max_pct": 2.0},
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is declared at {percent}, above the {max_pct} "
                "guideline. High sodium is the most common nutrition concern in "
                "street food."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Taste before adding salt",
                body="Sauces and packaged mixes already contain salt; do not add more by habit.",
                priority=60,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Refined Wheat Flour",
        category=IngredientCategory.CEREAL,
        risk=RiskLevel.LOW,
        description="Maida; refined flour without the bran or germ.",
        synonyms=[
            _syn("refined wheat flour"),
            _syn("maida"),
            _syn("white flour"),
            _syn("refined flour"),
            _syn("wheat flour"),
            _syn("मैदा"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} (maida) is a refined flour with most fibre "
                "removed. Low direct risk, but it is a highly refined "
                "carbohydrate."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Low concern",
                body="Consider offering a whole-wheat option alongside.",
                priority=95,
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # Antioxidants and emulsifiers
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="TBHQ",
        category=IngredientCategory.ANTIOXIDANT,
        risk=RiskLevel.MODERATE,
        description="Synthetic antioxidant added to frying oils and snacks.",
        synonyms=[
            _syn("tbhq"),
            _syn("tertiary butylhydroquinone"),
            _syn("tert-butylhydroquinone"),
            _e("E319"),
            _ins("INS 319"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is a synthetic antioxidant added to stop oils "
                "going rancid. It has a permitted maximum level that varies by "
                "product."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Check the declared level",
                body="Ask the supplier for the TBHQ level in this product.",
                priority=50,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Soy Lecithin",
        category=IngredientCategory.EMULSIFIER,
        risk=RiskLevel.LOW,
        description="Emulsifier derived from soy; a soy allergen source.",
        synonyms=[
            _syn("soy lecithin"),
            _syn("soya lecithin"),
            _syn("lecithin"),
            _e("E322"),
            _ins("INS 322"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is an emulsifier derived from soy. Low risk, but "
                "it is a soy allergen and must be declared for customers with "
                "soy allergy."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Declare the soy allergen",
                body="Customers with a soy allergy need to see this declared.",
                priority=40,
            ),
        ],
    ),
    IngredientSeed(
        canonical_name="Citric Acid",
        category=IngredientCategory.ACIDITY_REGULATOR,
        risk=RiskLevel.LOW,
        description="Acidity regulator and mild preservative.",
        synonyms=[
            _syn("citric acid"),
            _syn("acidity regulator"),
            _e("E330"),
            _ins("INS 330"),
        ],
        rule=RuleSeed(
            rule_type=RuleType.PRESENCE,
            status=ScanStatus.POTENTIAL_CONCERN,
            template=(
                "{ingredient} is an acidity regulator. It is very low risk and "
                "widely used, but it is still an added additive."
            ),
        ),
        recommendations=[
            RecommendationSeed(
                title="Low concern",
                body="No action needed.",
                priority=99,
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # Rule-free ingredients.
    # These exist so the pipeline can actually reach "Suitable": without at
    # least a few benign, matchable ingredients, every scan that matches
    # anything would produce a concern and the status would be untestable.
    # ------------------------------------------------------------------
    IngredientSeed(
        canonical_name="Turmeric",
        category=IngredientCategory.SPICE,
        risk=RiskLevel.LOW,
        description="Common Indian spice used for colour and flavour.",
        synonyms=[
            _syn("turmeric"),
            _syn("haldi"),
            _syn("turmeric powder"),
            # Devanagari aliases matter: labels sold in Maharashtra and the
            # Hindi belt often print the declaration only in Devanagari, and
            # that is exactly the label a street vendor photographs.
            _syn("हल्दी"),
            _syn("हळद"),
        ],
    ),
    IngredientSeed(
        canonical_name="Mustard Oil",
        category=IngredientCategory.FAT_OIL,
        risk=RiskLevel.LOW,
        description="Traditional cold-pressed oil, common in Indian cooking.",
        synonyms=[
            _syn("mustard oil"),
            _syn("kachi ghani mustard oil"),
            _syn("sarson oil"),
            _syn("सरसों तेल"),
            _syn("मोहरी तेल"),
        ],
    ),
    IngredientSeed(
        canonical_name="Milk Solids",
        category=IngredientCategory.DAIRY,
        risk=RiskLevel.LOW,
        description="Dried milk component used in sweets and beverages.",
        synonyms=[
            _syn("milk solids"),
            _syn("dried milk"),
            _syn("milk powder"),
            _syn("skimmed milk powder"),
            _syn("दूध पाउडर"),
        ],
    ),
    IngredientSeed(
        canonical_name="Whey Powder",
        category=IngredientCategory.DAIRY,
        risk=RiskLevel.LOW,
        description="Dairy by-product used as a bulking agent.",
        synonyms=[_syn("whey powder"), _syn("whey"), _syn("whey protein")],
    ),
]


def rule_bearing_ingredients() -> List[IngredientSeed]:
    return [item for item in SEED_INGREDIENTS if item.rule is not None]


def rule_free_ingredients() -> List[IngredientSeed]:
    return [item for item in SEED_INGREDIENTS if item.rule is None]
