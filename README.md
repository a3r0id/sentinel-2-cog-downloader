# Sentinel-2 COG Downloader/Loader

Search Element 84 Earth Search for Sentinel-2 L2A Cloud-Optimized GeoTIFFs, stitch every tile needed for **full bounding-box coverage**, keep only the bands you ask for, and return an `xarray` array.
I know this is a bit niche but I've found myself writing this code multiple times over the years so I'm putting it in a package. View on [PyPi](https://pypi.org/project/sentinel-2-cog-downloader/).

## Install

```bash
pip install sentinel-2-cog-downloader
```

**Or with [uv](https://docs.astral.sh/uv/):**

```bash
uv add sentinel-2-cog-downloader
```

## Usage

```python
from s2_cog_dl import Downloader, NoViableDataError

downloader = Downloader(
    bbox=[-122.86, 37.61, -122.15, 38.11],  # west, south, east, north
    datetime="2026-01-01",                  # target time; ±14 days by default
    bands=["red", "green", "blue", "nir"],  # or Sentinel-2 aliases like "B04"
    max_cloud_coverage=25,
)

try:
    result = downloader.download()
except NoViableDataError as exc:
    raise

array = result.to_array()   # DataArray with a "band" dimension
dataset = result.to_dataset()
```

A single date is expanded by `search_window_days` (default 14). Pass an explicit range to search only that window:

```python
Downloader(bbox=bbox, datetime=["2026-01-01", "2026-01-15"])
```

Output CRS defaults to the UTM zone of the bbox. Pixel size is metres (`resolution=10`) and is converted to degrees when `crs="EPSG:4326"`.
