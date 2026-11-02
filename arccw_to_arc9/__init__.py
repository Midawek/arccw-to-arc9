"""
ArcCW to ARC9 Converter Package
Convert Garry's Mod Arctic's Custom Weapons (ArcCW) to ARC9
"""
__version__ = "1.0.0"

from .weapon_converter import WeaponConverter
from .attachment_converter import AttachmentConverter
from .addon_converter import AddonConverter
from .bulk_converter import BulkConverter, detect_arccw_addons, is_arccw_addon_dir

__all__ = [
    "WeaponConverter",
    "AttachmentConverter",
    "AddonConverter",
    "BulkConverter",
    "detect_arccw_addons",
    "is_arccw_addon_dir"
]
