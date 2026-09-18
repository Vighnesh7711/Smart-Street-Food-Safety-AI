from app.db.base_class import Base
from app.models.user import User
from app.models.vendor import Vendor
from app.models.stall import Stall
from app.models.product import Product
from app.models.food_item import FoodItem
from app.models.ingredient import Ingredient, IngredientSynonym
from app.models.ingredient_rule import IngredientRule, Recommendation
from app.models.product_ingredient import ProductIngredient
from app.models.hygiene_indicator import HygieneIndicator
from app.models.hygiene_check import HygieneCheck
from app.models.stall_image import StallImage
from app.models.hygiene_score import HygieneScore
from app.models.qr_code import QrCode
from app.models.flag import Flag
from app.models.consumer_report import ConsumerReport
from app.models.audit_log import AuditLog
from app.models.analytics import AnalyticsAggregate

# Re-exported so `from app.db.base import Base` is enough for Alembic's
# autogenerate to see every table.
__all__ = [
    "Base",
    "User",
    "Vendor",
    "Stall",
    "Product",
    "FoodItem",
    "Ingredient",
    "IngredientSynonym",
    "IngredientRule",
    "Recommendation",
    "ProductIngredient",
    "HygieneIndicator",
    "HygieneCheck",
    "StallImage",
    "HygieneScore",
    "QrCode",
    "Flag",
    "ConsumerReport",
    "AuditLog",
    "AnalyticsAggregate",
]
