"""Slideshow Pro - Visualizador de fotos moderno, resiliente e extensível."""

__version__ = "1.2.0"

from slideshow.app import SlideshowApp
from slideshow.core import run_slideshow, find_image_files
from slideshow.vault import OneDriveVaultManager, diagnose_path
from slideshow.display import FramingMode, TransitionMode, SortOrder, CaptionMode
from slideshow.favorites import FavoritesManager
from slideshow.buffer import RAMImageBuffer

__all__ = [
    "__version__",
    "SlideshowApp",
    "run_slideshow",
    "find_image_files",
    "OneDriveVaultManager",
    "diagnose_path",
    "FramingMode",
    "TransitionMode",
    "SortOrder",
    "CaptionMode",
    "FavoritesManager",
    "RAMImageBuffer",
]
