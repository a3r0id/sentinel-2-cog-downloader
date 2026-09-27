ELEMENT_84_COGS_BUCKET = "sentinel-cogs"
ELEMENT_84_STAC_URL = "https://earth-search.aws.element84.com/v1"
ELEMENT_84_SENTINEL_S2_L2A_COLLECTION = "sentinel-2-l2a"

DEFAULT_MAX_CLOUD_COVER = 25.0
DEFAULT_RESOLUTION_M = 10.0
DEFAULT_SEARCH_WINDOW_DAYS = 14
DEFAULT_MIN_COVERAGE = 0.99
DEFAULT_GROUPBY = "solar_day"

# Earth Search v1 COG asset names (not the *-jp2 originals).
DEFAULT_BANDS = ("red", "green", "blue", "nir")
S2_COG_BANDS = (
    "coastal",
    "blue",
    "green",
    "red",
    "rededge1",
    "rededge2",
    "rededge3",
    "nir",
    "nir08",
    "nir09",
    "swir16",
    "swir22",
    "scl",
    "aot",
    "wvp",
    "visual",
)

# Common Sentinel-2 aliases -> Earth Search v1 asset keys.
BAND_ALIASES = {
    "b01": "coastal",
    "b1": "coastal",
    "coastal": "coastal",
    "b02": "blue",
    "b2": "blue",
    "blue": "blue",
    "b03": "green",
    "b3": "green",
    "green": "green",
    "b04": "red",
    "b4": "red",
    "red": "red",
    "b05": "rededge1",
    "b5": "rededge1",
    "rededge1": "rededge1",
    "re1": "rededge1",
    "b06": "rededge2",
    "b6": "rededge2",
    "rededge2": "rededge2",
    "re2": "rededge2",
    "b07": "rededge3",
    "b7": "rededge3",
    "rededge3": "rededge3",
    "re3": "rededge3",
    "b08": "nir",
    "b8": "nir",
    "nir": "nir",
    "b8a": "nir08",
    "nir08": "nir08",
    "nir8a": "nir08",
    "b09": "nir09",
    "b9": "nir09",
    "nir09": "nir09",
    "b11": "swir16",
    "swir16": "swir16",
    "swir1": "swir16",
    "b12": "swir22",
    "swir22": "swir22",
    "swir2": "swir22",
    "scl": "scl",
    "aot": "aot",
    "wvp": "wvp",
    "visual": "visual",
    "rgb": "visual",
}
