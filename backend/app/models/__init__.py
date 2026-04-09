"""
PetCircle Phase 1 — SQLAlchemy Models Package

All models are imported here to ensure they are registered with
SQLAlchemy's declarative base. This is required for relationship
resolution and for alembic/migration tooling to discover all tables.
"""

from app.models.agent_order_session import AgentOrderSession
from app.models.breed_consequence_library import BreedConsequenceLibrary
from app.models.cart_item import CartItem
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.conflict_flag import ConflictFlag
from app.models.contact import Contact
from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.dashboard_token import DashboardToken
from app.models.dashboard_visit import DashboardVisit
from app.models.deferred_care_plan_pending import DeferredCarePlanPending
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.diet_item import DietItem
from app.models.document import Document
from app.models.food_nutrition_cache import FoodNutritionCache
from app.models.hygiene_preference import HygienePreference
from app.models.hygiene_tip_cache import HygieneTipCache
from app.models.ideal_weight_cache import IdealWeightCache
from app.models.message_log import MessageLog
from app.models.nudge import Nudge
from app.models.nudge_config import NudgeConfig
from app.models.nudge_delivery_log import NudgeDeliveryLog
from app.models.nudge_engagement import NudgeEngagement
from app.models.nudge_message_library import NudgeMessageLibrary
from app.models.nutrition_target_cache import NutritionTargetCache
from app.models.order import Order
from app.models.order_recommendation import OrderRecommendation
from app.models.pet import Pet
from app.models.pet_life_stage_trait import PetLifeStageTrait
from app.models.pet_preference import PetPreference
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.product_food import ProductFood
from app.models.product_supplement import ProductSupplement
from app.models.reminder import Reminder
from app.models.shown_fun_fact import ShownFunFact
from app.models.user import User
from app.models.weight_history import WeightHistory

__all__ = [
    "User",
    "Pet",
    "PetLifeStageTrait",
    "PreventiveMaster",
    "PreventiveRecord",
    "Reminder",
    "Document",
    "MessageLog",
    "DashboardToken",
    "DeferredCarePlanPending",
    "ConflictFlag",
    "ShownFunFact",
    "DiagnosticTestResult",
    "Order",
    "OrderRecommendation",
    "PetPreference",
    "Condition",
    "ConditionMedication",
    "ConditionMonitoring",
    "Contact",
    "WeightHistory",
    "DietItem",
    "HygienePreference",
    "ProductFood",
    "ProductSupplement",
    "Nudge",
    "NudgeConfig",
    "NudgeDeliveryLog",
    "NudgeEngagement",
    "CartItem",
    "IdealWeightCache",
    "NutritionTargetCache",
    "FoodNutritionCache",
    "HygieneTipCache",
    "CustomPreventiveItem",
    "NudgeMessageLibrary",
    "BreedConsequenceLibrary",
    "DashboardVisit",
    "AgentOrderSession",
]
