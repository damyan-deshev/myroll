from __future__ import annotations

import hashlib
import os
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from backend.app.settings import Settings


MAX_ASSET_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000
CHUNK_SIZE = 1024 * 1024

IMAGE_FORMATS = {
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "WEBP": ("image/webp", "webp"),
}

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class AssetImportError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StoredImage:
    checksum: str
    relative_path: str
    mime_type: str
    byte_size: int
    width: int
    height: int
    original_filename: str | None


def _safe_original_filename(value: str | None) -> str | None:
    if not value:
        return None
    name = Path(value).name.strip()
    return name or None


def _validate_image(path: Path) -> tuple[str, str, int, int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                image_format = (image.format or "").upper()
                if image_format not in IMAGE_FORMATS:
                    raise AssetImportError(400, "unsupported_image_format", "Unsupported image format")
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise AssetImportError(400, "invalid_image", "Invalid image dimensions")
                if width * height > MAX_IMAGE_PIXELS:
                    raise AssetImportError(413, "image_too_large", "Image dimensions exceed limit")
                mime_type, extension = IMAGE_FORMATS[image_format]
                return mime_type, extension, width, height
    except AssetImportError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise AssetImportError(413, "image_too_large", "Image dimensions exceed limit") from None
    except (UnidentifiedImageError, OSError, ValueError):
        raise AssetImportError(400, "invalid_image", "File is not a valid supported image") from None


def store_image_stream(settings: Settings, source: BinaryIO, original_filename: str | None) -> StoredImage:
    settings.ensure_directories()
    tmp_dir = settings.asset_dir / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    hasher = hashlib.sha256()
    byte_size = 0
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(prefix="myroll-asset-", suffix=".tmp", dir=tmp_dir, delete=False) as temp:
            temp_path = Path(temp.name)
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                byte_size += len(chunk)
                if byte_size > MAX_ASSET_BYTES:
                    raise AssetImportError(413, "asset_too_large", "Asset exceeds 25 MB limit")
                hasher.update(chunk)
                temp.write(chunk)

        if byte_size <= 0 or temp_path is None:
            raise AssetImportError(400, "empty_asset", "Asset file is empty")

        mime_type, extension, width, height = _validate_image(temp_path)
        checksum = hasher.hexdigest()
        relative_path = Path(checksum[:2]) / f"{checksum}.{extension}"
        final_path = settings.asset_dir / relative_path
        final_path.parent.mkdir(parents=True, exist_ok=True)

        if final_path.exists():
            temp_path.unlink(missing_ok=True)
        else:
            os.replace(temp_path, final_path)

        return StoredImage(
            checksum=checksum,
            relative_path=relative_path.as_posix(),
            mime_type=mime_type,
            byte_size=byte_size,
            width=width,
            height=height,
            original_filename=_safe_original_filename(original_filename),
        )
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def store_image_path(settings: Settings, source_path: Path) -> StoredImage:
    try:
        with source_path.expanduser().resolve().open("rb") as source:
            return store_image_stream(settings, source, source_path.name)
    except AssetImportError:
        raise
    except FileNotFoundError:
        raise AssetImportError(404, "source_file_not_found", "Source file not found") from None
    except IsADirectoryError:
        raise AssetImportError(400, "source_file_invalid", "Source path is not a file") from None
    except OSError:
        raise AssetImportError(400, "source_file_unreadable", "Source file could not be read") from None


def resolve_asset_path(settings: Settings, relative_path: str) -> Path:
    asset_root = settings.asset_dir.resolve()
    candidate = (asset_root / relative_path).resolve()
    try:
        candidate.relative_to(asset_root)
    except ValueError:
        raise AssetImportError(500, "asset_path_invalid", "Asset path is invalid") from None
    return candidate
