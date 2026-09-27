from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

import xarray as xr
from odc.stac import configure_rio
from odc.stac import load as odc_load
from pystac import Item
from pystac_client import Client

from .constants import (
    DEFAULT_BANDS,
    DEFAULT_GROUPBY,
    DEFAULT_MAX_CLOUD_COVER,
    DEFAULT_MIN_COVERAGE,
    DEFAULT_RESOLUTION_M,
    DEFAULT_SEARCH_WINDOW_DAYS,
    ELEMENT_84_SENTINEL_S2_L2A_COLLECTION,
    ELEMENT_84_STAC_URL,
)
from .types import BandType, BBoxType, ChunksType, CRSType, DateType
from .utils import (
    NoViableDataError,
    bbox_coverage,
    item_cloud_cover,
    item_datetime,
    normalize_datetime,
    resolution_in_crs_units,
    resolve_bands,
    solar_day_key,
    target_datetime,
    utm_crs_from_bbox,
)

_RIO_CONFIGURED = False


def ensure_rio_config() -> None:
    """GDAL/rasterio settings for public Element 84 COGs (unsigned S3)."""
    global _RIO_CONFIGURED
    if _RIO_CONFIGURED:
        return
    configure_rio(cloud_defaults=True, aws={"aws_unsigned": True})
    _RIO_CONFIGURED = True


@dataclass
class SceneGroup:
    """Tiles from one solar day that together cover the AOI."""

    key: str
    items: List[Item]
    datetime: datetime
    coverage: float
    cloud_cover: float


class DownloaderResult:
    """
    One mosaicked Sentinel-2 scene covering the requested bbox.

    Load pixels with :meth:`to_array` (stacked ``band`` dimension) or
    :meth:`to_dataset` (one variable per band).
    """

    def __init__(
        self,
        group: SceneGroup,
        bbox: BBoxType,
        crs: CRSType,
        resolution: float,
        bands: Sequence[str],
        groupby: str = DEFAULT_GROUPBY,
        chunks: ChunksType = None,
    ):
        self.group = group
        self.items = list(group.items)
        self.bbox = bbox
        self.crs = crs
        self.resolution = resolution
        self.bands = list(bands)
        self.groupby = groupby
        self.chunks = chunks

    @property
    def datetime(self) -> datetime:
        return self.group.datetime

    @property
    def coverage(self) -> float:
        return self.group.coverage

    @property
    def cloud_cover(self) -> float:
        return self.group.cloud_cover

    def _squeeze_scene_time(self, obj: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
        if "time" in obj.dims and obj.sizes["time"] == 1:
            obj = obj.squeeze("time", drop=True)
        obj.attrs.setdefault("datetime", self.datetime.isoformat())
        obj.attrs.setdefault("cloud_cover", self.cloud_cover)
        obj.attrs.setdefault("coverage", self.coverage)
        return obj

    def to_dataset(self, bands: Optional[BandType] = None) -> xr.Dataset:
        """Load selected COG bands, clipped and stitched to the bbox."""
        ensure_rio_config()
        load_bands = resolve_bands(bands if bands is not None else self.bands)
        load_kwargs = {
            "bands": load_bands,
            "bbox": tuple(self.bbox),
            "crs": self.crs,
            "resolution": self.resolution,
            "groupby": self.groupby,
        }
        if self.chunks is not None:
            load_kwargs["chunks"] = self.chunks
        return self._squeeze_scene_time(odc_load(self.items, **load_kwargs))

    def to_array(self, bands: Optional[BandType] = None) -> xr.DataArray:
        """Same as :meth:`to_dataset`, stacked on a ``band`` dimension."""
        return self._squeeze_scene_time(self.to_dataset(bands=bands).to_array(dim="band"))

    def toODC(self, bands: Optional[BandType] = None) -> xr.Dataset:
        return self.to_dataset(bands=bands)

    def toArray(self, bands: Optional[BandType] = None) -> xr.DataArray:
        return self.to_array(bands=bands)


class Downloader:
    """
    Search Element 84 STAC for Sentinel-2 L2A COGs, pick the scene closest
    to a target time that fully covers ``bbox``, and stitch tiles into one array.

    Parameters
    ----------
    bbox:
        WGS84 bounding box ``[west, south, east, north]``.
    datetime:
        Target timestamp, or an explicit ``start/end`` search window.
        A single date is expanded by ``search_window_days`` on each side.
    crs:
        Output CRS. ``None`` selects the UTM zone of the bbox centroid.
    bands:
        COG bands to keep (Earth Search names or Sentinel-2 aliases like ``B04``).
    max_cloud_coverage:
        Maximum ``eo:cloud_cover`` (%) allowed for any tile used in the mosaic.
    resolution:
        Output pixel size in metres. Converted to degrees when ``crs`` is geographic.
    search_window_days:
        Half-window used when ``datetime`` is a single timestamp.
    min_coverage:
        Required fraction of ``bbox`` covered by tile footprints (0–1).
    chunks:
        Optional Dask chunks for ``odc.stac.load``.
    groupby:
        odc-stac grouping key; ``solar_day`` stitches same-day tiles.

    Usage
    -----
    ```python
    downloader = Downloader(
        bbox=[-122.86, 37.61, -122.15, 38.11],
        datetime="2026-01-01",
        bands=["red", "green", "blue"],
    )
    result = downloader.download()
    array = result.to_array()
    ```
    """

    def __init__(
        self,
        bbox: BBoxType,
        datetime: DateType,
        crs: CRSType = None,
        bands: BandType = DEFAULT_BANDS,
        max_cloud_coverage: float = DEFAULT_MAX_CLOUD_COVER,
        resolution: float = DEFAULT_RESOLUTION_M,
        search_window_days: int = DEFAULT_SEARCH_WINDOW_DAYS,
        min_coverage: float = DEFAULT_MIN_COVERAGE,
        chunks: ChunksType = None,
        groupby: str = DEFAULT_GROUPBY,
    ):
        if len(bbox) != 4:
            raise ValueError("bbox must be [west, south, east, north]")
        self.bbox = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        self.datetime_spec = datetime
        self.search_window_days = search_window_days
        self.datetime_str = normalize_datetime(datetime, search_window_days)
        self.target_dt = target_datetime(datetime)
        self.crs = crs if crs is not None else utm_crs_from_bbox(self.bbox)
        self.resolution_m = float(resolution)
        self.resolution = resolution_in_crs_units(self.crs, self.bbox, self.resolution_m)
        self.bands = resolve_bands(bands)
        self.max_cloud_coverage = float(max_cloud_coverage)
        self.min_coverage = float(min_coverage)
        self.chunks = chunks
        self.groupby = groupby
        self.items: List[Item] = []
        self.client = Client.open(ELEMENT_84_STAC_URL)
        ensure_rio_config()

    def search(self) -> List[Item]:
        """All Sentinel-2 L2A items intersecting the bbox in the search window."""
        search = self.client.search(
            collections=[ELEMENT_84_SENTINEL_S2_L2A_COLLECTION],
            bbox=self.bbox,
            datetime=self.datetime_str,
        )
        self.items = list(search.items())
        return self.items

    def select(self, items: Optional[Sequence[Item]] = None) -> SceneGroup:
        """
        Choose the solar-day mosaic closest to the target time that fully
        covers the bbox with acceptable cloud cover.
        """
        candidates = list(items if items is not None else (self.items or self.search()))
        if not candidates:
            raise NoViableDataError(
                f"No Sentinel-2 L2A items found for bbox={self.bbox} "
                f"datetime={self.datetime_str}"
            )

        groups = self._group_items(candidates)
        viable: List[SceneGroup] = []
        best_coverage = 0.0
        least_cloud = 100.0
        for group in groups:
            best_coverage = max(best_coverage, group.coverage)
            if group.coverage >= self.min_coverage:
                least_cloud = min(least_cloud, group.cloud_cover)
            if group.coverage >= self.min_coverage and group.cloud_cover <= self.max_cloud_coverage:
                viable.append(group)

        if not viable:
            raise NoViableDataError(
                "No viable Sentinel-2 mosaic for "
                f"bbox={self.bbox} datetime={self.datetime_str}: "
                f"best footprint coverage={best_coverage:.1%}, "
                f"lowest cloud cover among full-cover days={least_cloud:.1f}%, "
                f"required coverage>={self.min_coverage:.1%}, "
                f"max cloud<={self.max_cloud_coverage:.1f}%."
            )

        return min(viable, key=lambda g: (abs(g.datetime - self.target_dt), g.cloud_cover))

    def download(self, bands: Optional[BandType] = None) -> DownloaderResult:
        """Select the closest viable mosaic; pixels are loaded via the result object."""
        group = self.select()
        return DownloaderResult(
            group=group,
            bbox=self.bbox,
            crs=self.crs,
            resolution=self.resolution,
            bands=resolve_bands(bands if bands is not None else self.bands),
            groupby=self.groupby,
            chunks=self.chunks,
        )

    def _group_items(self, items: Sequence[Item]) -> List[SceneGroup]:
        buckets: dict[str, List[Item]] = {}
        for item in items:
            buckets.setdefault(solar_day_key(item), []).append(item)

        groups: List[SceneGroup] = []
        for key, grouped in buckets.items():
            times = [item_datetime(item) for item in grouped]
            clouds = [item_cloud_cover(item) for item in grouped]
            groups.append(
                SceneGroup(
                    key=key,
                    items=list(grouped),
                    datetime=min(times),
                    coverage=bbox_coverage(grouped, self.bbox),
                    cloud_cover=max(clouds) if clouds else 100.0,
                )
            )
        return groups
