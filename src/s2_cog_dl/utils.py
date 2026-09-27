import re
from datetime import datetime, timedelta, timezone
from math import cos, radians
from typing import Iterable, List, Sequence

from pystac import Item
from shapely.geometry import box, shape
from shapely.ops import unary_union

from .constants import BAND_ALIASES, S2_COG_BANDS
from .types import BBoxType, CRSType, DateType


class NoViableDataError(LookupError):
    """No Sentinel-2 mosaic fully covers the AOI with acceptable cloud cover."""


def parse_bbox(value: str) -> List[float]:
    """Parse BBOX=west,south,east,north from .env into four floats."""
    parts = [float(x.strip()) for x in value.split(",")]
    if len(parts) != 4:
        raise ValueError(f"BBOX must have 4 comma-separated floats, got: {value!r}")
    return parts


def parse_iso_datetime(value: str) -> datetime:
    """Parse a date or ISO-8601 timestamp into an aware UTC datetime."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _range_parts(datetime_spec: DateType) -> tuple[str, str | None]:
    if isinstance(datetime_spec, str):
        if "/" in datetime_spec:
            start, end = datetime_spec.split("/", 1)
            return start.strip(), end.strip()
        return datetime_spec.strip(), None
    if isinstance(datetime_spec, (list, tuple)):
        if len(datetime_spec) == 1:
            return str(datetime_spec[0]).strip(), None
        if len(datetime_spec) == 2:
            return str(datetime_spec[0]).strip(), str(datetime_spec[1]).strip()
    raise TypeError("datetime must be a string or a (start, end) pair")


def target_datetime(datetime_spec: DateType) -> datetime:
    """Instant to match against: a single timestamp, or the start of a range."""
    start, _ = _range_parts(datetime_spec)
    return parse_iso_datetime(start)


def normalize_datetime(datetime_spec: DateType, search_window_days: int = 0) -> str:
    """STAC datetime filter: keep an explicit range, or expand a single timestamp."""
    start, end = _range_parts(datetime_spec)
    if end is not None:
        return f"{start}/{end}"
    if search_window_days <= 0:
        return start
    target = parse_iso_datetime(start)
    delta = timedelta(days=search_window_days)
    lo = (target - delta).date().isoformat()
    hi = (target + delta).date().isoformat()
    return f"{lo}/{hi}"


def format_crs(crs: CRSType) -> str:
    """Compact CRS label, e.g. EPSG:3857."""
    if crs is None:
        return "n/a"
    epsg = getattr(crs, "to_epsg", lambda: None)()
    if epsg is None:
        epsg = getattr(crs, "epsg", None)
    if epsg is not None:
        return f"EPSG:{int(epsg)}"
    text = str(crs)
    match = re.search(r'ID\["EPSG",\s*(\d+)\]', text) or re.search(r"EPSG[:\s]*(\d+)", text, re.I)
    if match:
        return f"EPSG:{match.group(1)}"
    return text if len(text) <= 48 else text[:45] + "..."


def utm_crs_from_bbox(bbox: BBoxType) -> str:
    """UTM EPSG code for the bbox centroid (WGS84)."""
    west, south, east, north = bbox
    lon = (west + east) / 2.0
    lat = (south + north) / 2.0
    zone = int((lon + 180) // 6) + 1
    zone = min(max(zone, 1), 60)
    return f"EPSG:{32600 + zone}" if lat >= 0 else f"EPSG:{32700 + zone}"


def _is_geographic_crs(crs: CRSType) -> bool:
    if crs is None:
        return False
    if isinstance(crs, int):
        return crs == 4326
    label = str(crs).upper().replace(" ", "")
    return label in {"EPSG:4326", "4326", "OGC:CRS84", "CRS84", "WGS84"}


def resolution_in_crs_units(crs: CRSType, bbox: BBoxType, resolution_m: float) -> float:
    """Convert a metre resolution into CRS units (degrees for EPSG:4326)."""
    if not _is_geographic_crs(crs):
        return resolution_m
    lat = (bbox[1] + bbox[3]) / 2.0
    metres_per_degree = 111_320.0 * max(cos(radians(lat)), 0.01)
    return resolution_m / metres_per_degree


def resolve_bands(bands: str | Sequence[str]) -> List[str]:
    """Map aliases (B04, nir, ...) onto Earth Search v1 COG asset names."""
    names = [bands] if isinstance(bands, str) else list(bands)
    resolved: List[str] = []
    seen = set()
    unknown: List[str] = []
    for raw in names:
        key = str(raw).strip()
        alias = BAND_ALIASES.get(key.lower(), key.lower())
        if alias not in S2_COG_BANDS:
            unknown.append(raw)
            continue
        if alias not in seen:
            seen.add(alias)
            resolved.append(alias)
    if unknown:
        raise ValueError(
            f"Unknown Sentinel-2 band(s): {unknown}. Valid names: {list(S2_COG_BANDS)}"
        )
    if not resolved:
        raise ValueError("At least one band is required")
    return resolved


def item_datetime(item: Item) -> datetime:
    if item.datetime is None:
        raise ValueError(f"STAC item {item.id!r} has no datetime")
    dt = item.datetime
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def item_cloud_cover(item: Item) -> float:
    value = item.properties.get("eo:cloud_cover")
    if value is None:
        return 100.0
    return float(value)


def solar_day_key(item: Item) -> str:
    """Group tiles from the same local/solar calendar day."""
    dt = item_datetime(item)
    lon = 0.0
    if item.bbox:
        lon = (item.bbox[0] + item.bbox[2]) / 2.0
    elif item.geometry:
        lon = shape(item.geometry).centroid.x
    solar = dt + timedelta(hours=lon / 15.0)
    return solar.date().isoformat()


def bbox_coverage(items: Iterable[Item], bbox: BBoxType) -> float:
    """Fraction of the WGS84 bbox covered by the union of item footprints."""
    aoi = box(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    if aoi.area <= 0:
        return 0.0
    geoms = [shape(item.geometry) for item in items if item.geometry]
    if not geoms:
        return 0.0
    intersection = unary_union(geoms).intersection(aoi)
    return float(intersection.area / aoi.area)
