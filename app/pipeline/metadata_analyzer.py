from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ExifTags, UnidentifiedImageError


EXIF_TAGS = {value: key for key, value in ExifTags.TAGS.items()}


def _read_exif_value(exif: Any, tag_name: str) -> Any:
    tag_id = EXIF_TAGS.get(tag_name)
    if tag_id is None:
        return None
    value = exif.get(tag_id)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)
    return value


def analyze_metadata(image_path: str | Path) -> dict[str, Any]:
    """Read basic EXIF with Pillow. Missing EXIF is a weak provenance signal only."""
    path = Path(image_path).expanduser()
    try:
        with Image.open(path) as image:
            exif = image.getexif()
    except FileNotFoundError:
        return {
            "checked": False,
            "has_exif": False,
            "camera_make": None,
            "camera_model": None,
            "software": None,
            "datetime_original": None,
            "error": "Image file does not exist.",
            "optional_interfaces": _optional_interfaces(),
        }
    except UnidentifiedImageError:
        return {
            "checked": False,
            "has_exif": False,
            "camera_make": None,
            "camera_model": None,
            "software": None,
            "datetime_original": None,
            "error": "File is not a readable image.",
            "optional_interfaces": _optional_interfaces(),
        }
    except Exception as exc:
        return {
            "checked": False,
            "has_exif": False,
            "camera_make": None,
            "camera_model": None,
            "software": None,
            "datetime_original": None,
            "error": f"Metadata read failed: {exc}",
            "optional_interfaces": _optional_interfaces(),
        }

    has_exif = bool(exif)
    return {
        "checked": True,
        "has_exif": has_exif,
        "camera_make": _read_exif_value(exif, "Make"),
        "camera_model": _read_exif_value(exif, "Model"),
        "software": _read_exif_value(exif, "Software"),
        "datetime_original": _read_exif_value(exif, "DateTimeOriginal")
        or _read_exif_value(exif, "DateTime"),
        "exif_field_count": int(len(exif)) if exif else 0,
        "missing_exif_note": None
        if has_exif
        else "No EXIF found. This limits provenance, but does not mean the image is AI-generated.",
        "optional_interfaces": _optional_interfaces(),
        "error": None,
    }


def _optional_interfaces() -> dict[str, dict[str, str]]:
    return {
        "exiftool": {
            "status": "optional_placeholder",
            "note": "Reserved for deeper EXIF/XMP/IPTC parsing in a later version.",
        },
        "c2pa": {
            "status": "optional_placeholder",
            "note": "Reserved for Content Credentials / C2PA manifest parsing.",
        },
    }

