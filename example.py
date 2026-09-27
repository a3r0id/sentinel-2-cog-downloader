from pathlib import Path
from odc.geo.cog import write_cog
from s2_cog_dl import Downloader

SF_BBOX = [-122.860107, 37.613358, -122.145996, 38.108703]
OUT = Path("sf_mosaic.tif")

if __name__ == "__main__":
    downloader = Downloader(
        bbox=SF_BBOX,
        datetime="2026-01-01",
        bands=["B04", "B03", "B02"],  # red, green, blue
        max_cloud_coverage=40.0,
        resolution=20,
        search_window_days=21,
    )

    result = downloader.download()
    mosaic = result.to_array()
    write_cog(mosaic, OUT, overwrite=True)

    print(
        f"Wrote {OUT.resolve()} "
        f"({result.datetime.date()}, {len(result.items)} tiles, "
        f"{result.coverage:.0%} coverage, {result.cloud_cover:.1f}% cloud)"
    )
