"""SQLAlchemy models. Import everything here so Alembic/metadata sees them."""
from app.models.blockdata import BlockDefinition
from app.models.game import GameState, TurnEvent
from app.models.hexmap import HexMap, HexTile
from app.models.enums import (
    BlueprintStatus,
    GridSize,
    HexTerrain,
    PreparedWorldStatus,
    RequirementType,
    Role,
)
from app.models.job import Job
from app.models.server import GameServer
from app.models.ship import Blueprint, BlueprintSlot, Requirement, ShipClass
from app.models.setting import AppSetting
from app.models.user import Session as UserSession
from app.models.user import User
from app.models.world import (
    GameMap,
    PreparedWorld,
    PreparedWorldAssignment,
    StartSlot,
    StartSlotClass,
)

__all__ = [
    "BlockDefinition",
    "GameState",
    "TurnEvent",
    "HexMap",
    "HexTile",
    "BlueprintStatus",
    "GridSize",
    "HexTerrain",
    "PreparedWorldStatus",
    "RequirementType",
    "Role",
    "Job",
    "GameServer",
    "Blueprint",
    "BlueprintSlot",
    "Requirement",
    "ShipClass",
    "AppSetting",
    "UserSession",
    "User",
    "GameMap",
    "PreparedWorld",
    "PreparedWorldAssignment",
    "StartSlot",
    "StartSlotClass",
]
