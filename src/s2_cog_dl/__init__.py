"""
S2 Cog DL - Sentinel-2 COG Downloader & Data Loader
2026 Chad Groom - MIT License
"""

__version__ = "0.1.0"
__all__ = [
    "Downloader",
    "DownloaderResult",
    "NoViableDataError",
    "SceneGroup",
]

from .downloader import Downloader, DownloaderResult, SceneGroup
from .utils import NoViableDataError
