from __future__ import annotations

from dataclasses import dataclass

from backend.app.db.seed_ids import deterministic_uuid


@dataclass(frozen=True)
class DefaultWidget:
    id: str
    kind: str
    title: str
    x: int
    y: int
    width: int
    height: int
    z_index: int
    config: dict[str, object]


def _widget_id(kind: str) -> str:
    return deterministic_uuid(f"workspace-widget:{kind}")


DEFAULT_WORKSPACE_WIDGETS: tuple[DefaultWidget, ...] = (
    DefaultWidget(_widget_id("backend_status"), "backend_status", "Backend Status", 24, 72, 320, 230, 10, {}),
    DefaultWidget(_widget_id("campaigns"), "campaigns", "Campaigns", 24, 326, 360, 380, 20, {}),
    DefaultWidget(_widget_id("sessions"), "sessions", "Sessions", 408, 72, 360, 300, 30, {}),
    DefaultWidget(_widget_id("scenes"), "scenes", "Scenes", 408, 396, 420, 360, 40, {}),
    DefaultWidget(_widget_id("runtime"), "runtime", "Runtime", 852, 72, 380, 330, 50, {}),
    DefaultWidget(_widget_id("player_display"), "player_display", "Player Display", 852, 426, 380, 330, 55, {}),
    DefaultWidget(_widget_id("scene_context"), "scene_context", "Scene Context", 852, 780, 420, 360, 56, {}),
    DefaultWidget(_widget_id("asset_library"), "asset_library", "Asset Library", 1256, 72, 430, 430, 58, {}),
    DefaultWidget(_widget_id("storage_demo"), "storage_demo", "Storage / Demo", 1256, 526, 420, 260, 59, {}),
    DefaultWidget(
        _widget_id("map_display"),
        "map_display",
        "Map Display",
        1710,
        72,
        460,
        340,
        60,
        {"placeholder": True, "future": "asset/map/player display slices"},
    ),
    DefaultWidget(
        _widget_id("notes"),
        "notes",
        "Notes",
        1256,
        436,
        360,
        300,
        70,
        {"placeholder": True, "future": "notes/snippets slice"},
    ),
    DefaultWidget(
        _widget_id("party_tracker"),
        "party_tracker",
        "Party Tracker",
        1336,
        760,
        360,
        250,
        80,
        {"placeholder": True, "future": "entities/custom fields slice"},
    ),
    DefaultWidget(
        _widget_id("combat_tracker"),
        "combat_tracker",
        "Combat Tracker",
        1720,
        72,
        360,
        320,
        90,
        {"placeholder": True, "future": "combat state slice"},
    ),
    DefaultWidget(
        _widget_id("dice_roller"),
        "dice_roller",
        "Dice Roller",
        1720,
        416,
        320,
        230,
        100,
        {"placeholder": True, "future": "local tool slice"},
    ),
)


DEFAULT_WIDGET_IDS = {widget.id for widget in DEFAULT_WORKSPACE_WIDGETS}
