from unittest import TestCase

from s2_cog_dl import Downloader, NoViableDataError

# San Francisco Bay — large enough to require multiple MGRS tiles.
SF_BBOX = [-122.860107, 37.613358, -122.145996, 38.108703]
SF_DATETIME = "2026-01-01"


class TestDownloader(TestCase):
    def test_downloader(self):
        downloader = Downloader(
            bbox=SF_BBOX,
            datetime=SF_DATETIME,
            crs="EPSG:4326",
            bands=["red", "green", "blue"],
            max_cloud_coverage=40.0,
            resolution=20,
            search_window_days=21,
        )

        items = downloader.search()
        self.assertGreater(len(items), 0)

        try:
            result = downloader.download()
        except NoViableDataError as exc:
            self.fail(str(exc))

        self.assertGreaterEqual(result.coverage, downloader.min_coverage)
        self.assertLessEqual(result.cloud_cover, downloader.max_cloud_coverage)
        self.assertGreaterEqual(len(result.items), 1)

        data_array = result.to_array()
        self.assertEqual(tuple(data_array["band"].values), ("red", "green", "blue"))
        spatial = set(data_array.dims)
        self.assertTrue({"x", "y"}.issubset(spatial) or {"longitude", "latitude"}.issubset(spatial))
        for dim in spatial - {"band"}:
            self.assertGreater(data_array.sizes[dim], 0)
        print(data_array)
