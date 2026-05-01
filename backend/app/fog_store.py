from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from backend.app.settings import Settings


MAX_BRUSH_RADIUS = 500
MAX_BRUSH_POINTS = 2048
MAX_OPERATIONS_PER_REQUEST = 16


class FogStoreError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FogRect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class FogPoint:
    x: float
    y: float


def fog_relative_path(mask_id: str) -> str:
    return (Path("fog") / f"{mask_id}.png").as_posix()


def resolve_fog_path(settings: Settings, relative_path: str) -> Path:
    fog_root = (settings.asset_dir / "fog").resolve()
    candidate = (settings.asset_dir / relative_path).resolve()
    try:
        candidate.relative_to(fog_root)
    except ValueError:
        raise FogStoreError(500, "fog_path_invalid", "Fog mask path is invalid") from None
    return candidate


def create_hidden_mask(settings: Settings, relative_path: str, width: int, height: int) -> None:
    save_mask_atomic(settings, relative_path, Image.new("L", (width, height), 0))


def load_mask(settings: Settings, relative_path: str, width: int, height: int) -> Image.Image:
    path = resolve_fog_path(settings, relative_path)
    if not path.exists() or not path.is_file():
        raise FogStoreError(404, "fog_mask_blob_not_found", "Fog mask blob not found")
    try:
        with Image.open(path) as image:
            mask = image.convert("L")
            mask.load()
    except OSError:
        raise FogStoreError(400, "fog_mask_invalid", "Fog mask is invalid") from None
    if mask.size != (width, height):
        raise FogStoreError(409, "fog_mask_dimension_mismatch", "Fog mask dimensions do not match map")
    return mask


def save_mask_atomic(settings: Settings, relative_path: str, mask: Image.Image) -> None:
    final_path = resolve_fog_path(settings, relative_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = final_path.parent / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="myroll-fog-", suffix=".png", dir=tmp_dir, delete=False) as temp:
            temp_path = Path(temp.name)
            mask.convert("L").save(temp, format="PNG")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, final_path)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _finite(value: float, code: str, message: str) -> float:
    if not math.isfinite(value):
        raise FogStoreError(400, code, message)
    return value


def normalize_rect(rect: FogRect, width: int, height: int) -> tuple[int, int, int, int] | None:
    x = _finite(float(rect.x), "invalid_fog_coordinates", "Fog coordinates must be finite")
    y = _finite(float(rect.y), "invalid_fog_coordinates", "Fog coordinates must be finite")
    rect_width = _finite(float(rect.width), "invalid_fog_coordinates", "Fog coordinates must be finite")
    rect_height = _finite(float(rect.height), "invalid_fog_coordinates", "Fog coordinates must be finite")
    if rect_width < 0:
        x += rect_width
        rect_width = abs(rect_width)
    if rect_height < 0:
        y += rect_height
        rect_height = abs(rect_height)
    if rect_width == 0 or rect_height == 0:
        raise FogStoreError(400, "invalid_fog_rect", "Fog rectangle must have area")
    left = max(0, min(width, math.floor(x)))
    top = max(0, min(height, math.floor(y)))
    right = max(0, min(width, math.ceil(x + rect_width)))
    bottom = max(0, min(height, math.ceil(y + rect_height)))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _validate_points(points: Iterable[FogPoint]) -> list[tuple[float, float]]:
    normalized = [
        (
            _finite(float(point.x), "invalid_fog_coordinates", "Fog coordinates must be finite"),
            _finite(float(point.y), "invalid_fog_coordinates", "Fog coordinates must be finite"),
        )
        for point in points
    ]
    if not normalized:
        raise FogStoreError(400, "invalid_fog_brush", "Brush operation requires at least one point")
    if len(normalized) > MAX_BRUSH_POINTS:
        raise FogStoreError(400, "fog_brush_too_many_points", "Brush operation has too many points")
    return normalized


def apply_rect(mask: Image.Image, rect: FogRect, *, reveal: bool) -> None:
    bounds = normalize_rect(rect, mask.width, mask.height)
    if bounds is None:
        return
    draw = ImageDraw.Draw(mask)
    draw.rectangle(bounds, fill=255 if reveal else 0)


def apply_brush(mask: Image.Image, points: Iterable[FogPoint], radius: float, *, reveal: bool) -> None:
    radius = _finite(float(radius), "invalid_fog_radius", "Brush radius must be finite")
    if radius < 1 or radius > MAX_BRUSH_RADIUS:
        raise FogStoreError(400, "invalid_fog_radius", "Brush radius must be between 1 and 500 map pixels")
    normalized = _validate_points(points)
    draw = ImageDraw.Draw(mask)
    fill = 255 if reveal else 0
    diameter = max(1, int(round(radius * 2)))
    if len(normalized) > 1:
        draw.line(normalized, fill=fill, width=diameter, joint="curve")
    for x, y in normalized:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def apply_all(mask: Image.Image, *, reveal: bool) -> None:
    draw = ImageDraw.Draw(mask)
    draw.rectangle((0, 0, mask.width, mask.height), fill=255 if reveal else 0)
