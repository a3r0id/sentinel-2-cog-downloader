from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pystac import Item

from s2_cog_dl.downloader import Downloader, SceneGroup
from s2_cog_dl.utils import (
    NoViableDataError,
    bbox_coverage,
    normalize_datetime,
    resolve_bands,
    target_datetime,
    utm_crs_from_bbox,
)


def _polygon(west, south, east, north):
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]],
    }


def _item(item_id, when, geom_bbox, cloud):
    west, south, east, north = geom_bbox
    return Item(
        id=item_id,
        datetime=when,
        bbox=list(geom_bbox),
        geometry=_polygon(west, south, east, north),
        properties={"eo:cloud_cover": cloud},
    )


AOI = (0.0, 0.0, 2.0, 1.0)
LEFT = (-0.1, -0.1, 1.1, 1.1)
RIGHT = (0.9, -0.1, 2.1, 1.1)
PARTIAL = (-0.1, -0.1, 0.5, 1.1)


class TestBandAndDatetimeHelpers(TestCase):
    def test_resolve_bands_aliases_and_dedupe(self):
        self.assertEqual(resolve_bands(["B04", "red", "B08"]), ["red", "nir"])

    def test_resolve_bands_rejects_unknown(self):
        with self.assertRaises(ValueError):
            resolve_bands(["not-a-band"])

    def test_normalize_expands_single_timestamp(self):
        self.assertEqual(
            normalize_datetime("2026-01-10", search_window_days=2),
            "2026-01-08/2026-01-12",
        )

    def test_normalize_keeps_explicit_range(self):
        self.assertEqual(
            normalize_datetime(["2026-01-01", "2026-01-02"], search_window_days=14),
            "2026-01-01/2026-01-02",
        )

    def test_target_datetime_uses_range_start(self):
        self.assertEqual(
            target_datetime(["2026-01-01", "2026-01-10"]),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_utm_zone_for_san_francisco(self):
        self.assertEqual(utm_crs_from_bbox([-122.5, 37.7, -122.3, 37.9]), "EPSG:32610")


class TestCoverage(TestCase):
    def test_two_tiles_cover_bbox(self):
        day = datetime(2026, 1, 1, 19, 0, tzinfo=timezone.utc)
        items = [
            _item("left", day, LEFT, 5),
            _item("right", day, RIGHT, 8),
        ]
        self.assertGreaterEqual(bbox_coverage(items, AOI), 0.99)

    def test_partial_tile_does_not_cover(self):
        day = datetime(2026, 1, 1, 19, 0, tzinfo=timezone.utc)
        items = [_item("partial", day, PARTIAL, 5)]
        self.assertLess(bbox_coverage(items, AOI), 0.5)


class TestDownloaderSelect(TestCase):
    def _downloader(self, **kwargs):
        with patch("s2_cog_dl.downloader.Client") as client_cls:
            client_cls.open.return_value = MagicMock()
            with patch("s2_cog_dl.downloader.ensure_rio_config"):
                return Downloader(bbox=AOI, datetime="2026-01-02", **kwargs)

    def test_picks_closest_full_cover_day(self):
        target_day = datetime(2026, 1, 2, 19, 0, tzinfo=timezone.utc)
        farther_day = datetime(2026, 1, 5, 19, 0, tzinfo=timezone.utc)
        items = [
            _item("near-l", target_day, LEFT, 10),
            _item("near-r", target_day, RIGHT, 12),
            _item("far-l", farther_day, LEFT, 1),
            _item("far-r", farther_day, RIGHT, 1),
        ]
        downloader = self._downloader(max_cloud_coverage=25)
        group = downloader.select(items)
        self.assertIsInstance(group, SceneGroup)
        self.assertEqual({item.id for item in group.items}, {"near-l", "near-r"})

    def test_skips_cloudy_day_even_if_closer(self):
        cloudy = datetime(2026, 1, 2, 19, 0, tzinfo=timezone.utc)
        clear = datetime(2026, 1, 4, 19, 0, tzinfo=timezone.utc)
        items = [
            _item("cloud-l", cloudy, LEFT, 80),
            _item("cloud-r", cloudy, RIGHT, 90),
            _item("clear-l", clear, LEFT, 5),
            _item("clear-r", clear, RIGHT, 6),
        ]
        group = self._downloader(max_cloud_coverage=25).select(items)
        self.assertEqual({item.id for item in group.items}, {"clear-l", "clear-r"})

    def test_errors_when_coverage_incomplete(self):
        day = datetime(2026, 1, 2, 19, 0, tzinfo=timezone.utc)
        items = [_item("partial", day, PARTIAL, 5)]
        with self.assertRaises(NoViableDataError):
            self._downloader().select(items)

    def test_errors_when_all_days_too_cloudy(self):
        day = datetime(2026, 1, 2, 19, 0, tzinfo=timezone.utc)
        items = [
            _item("l", day, LEFT, 80),
            _item("r", day, RIGHT, 90),
        ]
        with self.assertRaises(NoViableDataError):
            self._downloader(max_cloud_coverage=25).select(items)

    def test_errors_when_search_empty(self):
        with self.assertRaises(NoViableDataError):
            self._downloader().select([])
