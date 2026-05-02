from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from backend.app.settings import Settings


class BundledAssetPackError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class BundledGrid:
    cols: int
    rows: int
    feet_per_cell: int
    px_per_cell: int
    offset_x: float
    offset_y: float


@dataclass(frozen=True)
class BundledMap:
    id: str
    title: str
    file: str
    path: Path
    collection: str
    group: str
    category_key: str
    category_label: str
    category_path: str
    width: int
    height: int
    checksum_sha256: str
    tags: tuple[str, ...]
    grid: BundledGrid
    curation: dict[str, Any]
    provenance: dict[str, Any]


@dataclass(frozen=True)
class BundledPack:
    id: str
    title: str
    root: Path
    asset_count: int
    category_count: int
    collections: tuple[str, ...]
    maps: tuple[BundledMap, ...]


def clear_bundled_pack_cache() -> None:
    _load_bundled_packs_cached.cache_clear()


def load_bundled_packs(settings: Settings) -> tuple[BundledPack, ...]:
    roots = tuple(str(path) for path in settings.bundled_asset_pack_dirs)
    return _load_bundled_packs_cached(roots)


def find_bundled_map(settings: Settings, pack_id: str, asset_id: str) -> tuple[BundledPack, BundledMap]:
    for pack in load_bundled_packs(settings):
        if pack.id != pack_id:
            continue
        for bundled_map in pack.maps:
            if bundled_map.id == asset_id:
                return pack, bundled_map
        raise BundledAssetPackError("bundled_asset_not_found", "Bundled asset not found")
    raise BundledAssetPackError("bundled_pack_not_found", "Bundled asset pack not found")


@lru_cache(maxsize=16)
def _load_bundled_packs_cached(scan_roots: tuple[str, ...]) -> tuple[BundledPack, ...]:
    packs: list[BundledPack] = []
    seen_pack_ids: set[str] = set()
    for scan_root_raw in scan_roots:
        scan_root = Path(scan_root_raw)
        if not scan_root.exists():
            continue
        if not scan_root.is_dir():
            raise BundledAssetPackError("bundled_pack_root_invalid", "Bundled asset pack root is invalid")
        for candidate in sorted(scan_root.iterdir(), key=lambda item: item.name):
            if not candidate.is_dir() or not (candidate / "manifest.json").is_file():
                continue
            pack = _load_pack(candidate)
            if pack.id in seen_pack_ids:
                raise BundledAssetPackError("bundled_pack_duplicate", f"Duplicate bundled asset pack id: {pack.id}")
            seen_pack_ids.add(pack.id)
            packs.append(pack)
    return tuple(packs)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise BundledAssetPackError("bundled_pack_invalid", f"Invalid bundled asset pack JSON: {path.name}") from error
    if not isinstance(data, dict):
        raise BundledAssetPackError("bundled_pack_invalid", f"Invalid bundled asset pack JSON object: {path.name}")
    return data


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BundledAssetPackError("bundled_pack_invalid", f"Invalid bundled asset field: {field}")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BundledAssetPackError("bundled_pack_invalid", f"Invalid bundled asset field: {field}")
    return value


def _safe_relative(root: Path, relative_path: str, field: str) -> Path:
    candidate_raw = Path(relative_path)
    if candidate_raw.is_absolute():
        raise BundledAssetPackError("bundled_pack_invalid", f"Bundled path must be relative: {field}")
    root_resolved = root.resolve()
    candidate = (root_resolved / candidate_raw).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise BundledAssetPackError("bundled_pack_invalid", f"Bundled path escapes pack root: {field}") from None
    return candidate


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    except OSError as error:
        raise BundledAssetPackError("bundled_asset_unreadable", "Bundled asset could not be read") from error
    return hasher.hexdigest()


def _image_size(path: Path) -> tuple[str, int, int]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            return (image.format or "").upper(), image.width, image.height
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise BundledAssetPackError("bundled_asset_invalid_image", "Bundled asset is not a valid image") from error


def _grid(value: Any, field: str) -> BundledGrid:
    if not isinstance(value, dict):
        raise BundledAssetPackError("bundled_pack_invalid", f"Invalid grid: {field}")
    if value.get("type") != "square":
        raise BundledAssetPackError("bundled_pack_invalid", f"Bundled grid must be square: {field}")
    cols = _integer(value.get("cols"), f"{field}.cols")
    rows = _integer(value.get("rows"), f"{field}.rows")
    feet_per_cell = _integer(value.get("feetPerCell"), f"{field}.feetPerCell")
    px_per_cell = _integer(value.get("pxPerCell"), f"{field}.pxPerCell")
    offset_x = value.get("offsetX")
    offset_y = value.get("offsetY")
    if (
        isinstance(offset_x, bool)
        or not isinstance(offset_x, int | float)
        or isinstance(offset_y, bool)
        or not isinstance(offset_y, int | float)
    ):
        raise BundledAssetPackError("bundled_pack_invalid", f"Invalid grid offsets: {field}")
    if cols <= 0 or rows <= 0 or feet_per_cell <= 0 or px_per_cell <= 0:
        raise BundledAssetPackError("bundled_pack_invalid", f"Invalid grid dimensions: {field}")
    return BundledGrid(
        cols=cols,
        rows=rows,
        feet_per_cell=feet_per_cell,
        px_per_cell=px_per_cell,
        offset_x=float(offset_x),
        offset_y=float(offset_y),
    )


def _validate_category(root: Path, summary: dict[str, Any]) -> tuple[BundledGrid, set[str]]:
    category_key = _string(summary.get("categoryKey"), "category.categoryKey")
    category_path = _string(summary.get("categoryPath"), f"{category_key}.categoryPath")
    category_file = _safe_relative(root, f"{category_path}/category.json", f"{category_key}.categoryPath")
    if not category_file.is_file():
        raise BundledAssetPackError("bundled_category_missing", f"Bundled category missing: {category_key}")
    data = _load_json(category_file)
    if data.get("schemaVersion") != 1 or data.get("categoryKey") != category_key:
        raise BundledAssetPackError("bundled_category_invalid", f"Bundled category metadata mismatch: {category_key}")
    grid = _grid(data.get("grid"), f"{category_key}.grid")
    category_dir = category_file.parent
    ids: set[str] = set()
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise BundledAssetPackError("bundled_category_invalid", f"Bundled category assets invalid: {category_key}")
    for item in assets:
        if not isinstance(item, dict):
            raise BundledAssetPackError("bundled_category_invalid", f"Bundled category asset invalid: {category_key}")
        asset_id = _string(item.get("id"), f"{category_key}.assets.id")
        asset_file = _string(item.get("file"), f"{category_key}.assets.file")
        candidate = _safe_relative(category_dir, asset_file, f"{category_key}.assets.file")
        if not candidate.is_file():
            raise BundledAssetPackError("bundled_asset_missing", f"Bundled category asset file missing: {asset_id}")
        ids.add(asset_id)
    if len(ids) != int(summary.get("acceptedCount", len(ids))):
        raise BundledAssetPackError("bundled_category_invalid", f"Bundled category count mismatch: {category_key}")
    return grid, ids


def _validate_taxonomy(root: Path, category_paths: dict[str, str]) -> None:
    taxonomy_path = root / "taxonomy.json"
    if not taxonomy_path.is_file():
        raise BundledAssetPackError("bundled_taxonomy_missing", "Bundled taxonomy is missing")
    taxonomy = _load_json(taxonomy_path)
    if taxonomy.get("schemaVersion") != 1:
        raise BundledAssetPackError("bundled_taxonomy_invalid", "Bundled taxonomy schema is invalid")
    collections = taxonomy.get("collections")
    if not isinstance(collections, dict):
        raise BundledAssetPackError("bundled_taxonomy_invalid", "Bundled taxonomy collections are invalid")
    taxonomy_categories: dict[str, str] = {}
    for collection in collections.values():
        if not isinstance(collection, dict) or not isinstance(collection.get("groups"), dict):
            raise BundledAssetPackError("bundled_taxonomy_invalid", "Bundled taxonomy groups are invalid")
        for group in collection["groups"].values():
            if not isinstance(group, dict) or not isinstance(group.get("categories"), list):
                raise BundledAssetPackError("bundled_taxonomy_invalid", "Bundled taxonomy categories are invalid")
            for category in group["categories"]:
                if not isinstance(category, dict):
                    raise BundledAssetPackError("bundled_taxonomy_invalid", "Bundled taxonomy category is invalid")
                taxonomy_categories[_string(category.get("categoryKey"), "taxonomy.categoryKey")] = _string(category.get("path"), "taxonomy.path")
    if taxonomy_categories != category_paths:
        raise BundledAssetPackError("bundled_taxonomy_invalid", "Bundled taxonomy does not match manifest categories")


def _load_pack(root: Path) -> BundledPack:
    manifest = _load_json(root / "manifest.json")
    if manifest.get("schemaVersion") != 1:
        raise BundledAssetPackError("bundled_pack_invalid", "Bundled manifest schema is invalid")
    pack_id = _string(manifest.get("packId"), "packId")
    title = _string(manifest.get("title"), "title")
    categories_raw = manifest.get("categories")
    assets_raw = manifest.get("assets")
    if not isinstance(categories_raw, list) or not isinstance(assets_raw, list):
        raise BundledAssetPackError("bundled_pack_invalid", "Bundled manifest lists are invalid")

    category_grids: dict[str, BundledGrid] = {}
    category_asset_ids: dict[str, set[str]] = {}
    category_paths: dict[str, str] = {}
    for summary in categories_raw:
        if not isinstance(summary, dict):
            raise BundledAssetPackError("bundled_pack_invalid", "Bundled category summary is invalid")
        category_key = _string(summary.get("categoryKey"), "category.categoryKey")
        category_paths[category_key] = _string(summary.get("categoryPath"), f"{category_key}.categoryPath")
        category_grids[category_key], category_asset_ids[category_key] = _validate_category(root, summary)
    _validate_taxonomy(root, category_paths)

    maps: list[BundledMap] = []
    seen_ids: set[str] = set()
    for item in assets_raw:
        if not isinstance(item, dict):
            raise BundledAssetPackError("bundled_pack_invalid", "Bundled manifest asset is invalid")
        asset_id = _string(item.get("id"), "asset.id")
        if asset_id in seen_ids:
            raise BundledAssetPackError("bundled_pack_invalid", f"Duplicate bundled asset id: {asset_id}")
        seen_ids.add(asset_id)
        category_key = _string(item.get("categoryKey"), f"{asset_id}.categoryKey")
        if asset_id not in category_asset_ids.get(category_key, set()):
            raise BundledAssetPackError("bundled_pack_invalid", f"Bundled asset missing from category: {asset_id}")
        grid = _grid(item.get("grid"), f"{asset_id}.grid")
        category_grid = category_grids[category_key]
        if grid != category_grid:
            raise BundledAssetPackError("bundled_pack_invalid", f"Bundled asset grid does not match category: {asset_id}")
        image = item.get("image")
        checksum = item.get("checksum")
        if not isinstance(image, dict) or not isinstance(checksum, dict):
            raise BundledAssetPackError("bundled_pack_invalid", f"Bundled asset image/checksum invalid: {asset_id}")
        width = _integer(image.get("width"), f"{asset_id}.image.width")
        height = _integer(image.get("height"), f"{asset_id}.image.height")
        if image.get("gridless") is not True:
            raise BundledAssetPackError("bundled_pack_invalid", f"Bundled asset must be gridless: {asset_id}")
        if width != grid.cols * grid.px_per_cell or height != grid.rows * grid.px_per_cell:
            raise BundledAssetPackError("bundled_pack_invalid", f"Bundled asset dimensions do not match grid: {asset_id}")
        file_value = _string(item.get("file"), f"{asset_id}.file")
        path = _safe_relative(root, file_value, f"{asset_id}.file")
        if not path.is_file():
            raise BundledAssetPackError("bundled_asset_missing", f"Bundled asset file missing: {asset_id}")
        image_format, actual_width, actual_height = _image_size(path)
        if image_format != "WEBP" or actual_width != width or actual_height != height:
            raise BundledAssetPackError("bundled_asset_invalid_image", f"Bundled asset image metadata mismatch: {asset_id}")
        checksum_sha256 = _string(checksum.get("sha256"), f"{asset_id}.checksum.sha256")
        if _hash_file(path) != checksum_sha256:
            raise BundledAssetPackError("bundled_asset_checksum_mismatch", f"Bundled asset checksum mismatch: {asset_id}")
        tags = item.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise BundledAssetPackError("bundled_pack_invalid", f"Bundled asset tags invalid: {asset_id}")
        curation = item.get("curation")
        provenance = item.get("provenance")
        maps.append(
            BundledMap(
                id=asset_id,
                title=_string(item.get("title"), f"{asset_id}.title"),
                file=file_value,
                path=path,
                collection=_string(item.get("collection"), f"{asset_id}.collection"),
                group=Path(category_paths[category_key]).parent.name,
                category_key=category_key,
                category_label=_string(item.get("categoryLabel"), f"{asset_id}.categoryLabel"),
                category_path=_string(item.get("categoryPath"), f"{asset_id}.categoryPath"),
                width=width,
                height=height,
                checksum_sha256=checksum_sha256,
                tags=tuple(tags),
                grid=grid,
                curation=curation if isinstance(curation, dict) else {},
                provenance=provenance if isinstance(provenance, dict) else {},
            )
        )
    if len(maps) != _integer(manifest.get("assetCount"), "assetCount"):
        raise BundledAssetPackError("bundled_pack_invalid", "Bundled asset count does not match manifest")
    return BundledPack(
        id=pack_id,
        title=title,
        root=root,
        asset_count=len(maps),
        category_count=len(categories_raw),
        collections=tuple(sorted({item.collection for item in maps})),
        maps=tuple(sorted(maps, key=lambda item: (item.collection, item.category_label, item.title, item.id))),
    )
