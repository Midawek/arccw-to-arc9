"""
Bulk Converter module for ArcCW to ARC9
Handles batch scanning and conversion of multiple addons or files.
"""
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .addon_converter import AddonConverter
from .weapon_converter import WeaponConverter
from .attachment_converter import AttachmentConverter

def is_arccw_addon_dir(dir_path: Path) -> bool:
    """Checks whether a directory is likely an ArcCW addon directory."""
    if not dir_path.is_dir():
        return False

    # Check for lua/weapons containing arccw files
    weapons_dir = dir_path / "lua" / "weapons"
    if weapons_dir.exists() and weapons_dir.is_dir():
        for item in weapons_dir.iterdir():
            if item.name.lower().startswith("arccw_"):
                return True
            if item.is_file() and item.suffix == ".lua":
                try:
                    head = item.read_text(encoding="utf-8", errors="replace")[:1000]
                    if "arccw" in head.lower():
                        return True
                except Exception:
                    pass

    # Check for lua/arccw
    if (dir_path / "lua" / "arccw").exists():
        return True

    # Check addon.json
    addon_json = dir_path / "addon.json"
    if addon_json.exists():
        try:
            head = addon_json.read_text(encoding="utf-8", errors="replace")
            if "arccw" in head.lower():
                return True
        except Exception:
            pass

    return False

def detect_arccw_addons(search_dir: Union[str, Path]) -> List[Path]:
    """
    Scans a directory for ArcCW addon folders.
    If search_dir itself is an ArcCW addon, returns [search_dir].
    Otherwise, checks its subdirectories.
    """
    root = Path(search_dir).resolve()
    if not root.exists() or not root.is_dir():
        return []

    # If the root itself is an ArcCW addon
    if is_arccw_addon_dir(root):
        return [root]

    found: List[Path] = []
    # Check immediate children first
    for item in root.iterdir():
        if item.is_dir():
            if is_arccw_addon_dir(item):
                found.append(item)
            else:
                # Also check 1 level deeper (e.g. garrysmod/addons/addon_name)
                for sub in item.iterdir():
                    if sub.is_dir() and is_arccw_addon_dir(sub) and sub not in found:
                        found.append(sub)

    return found

class BulkConverter:
    """
    Manages batch conversion of multiple ArcCW addons or Lua files.
    """
    def __init__(
        self,
        items: List[Union[str, Path]],
        output_parent_dir: Optional[Union[str, Path]] = None,
        bulk_attachments: bool = True,
        copy_assets: bool = True,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        self.items = [Path(p).resolve() for p in items]
        self.output_parent_dir = Path(output_parent_dir).resolve() if output_parent_dir else None
        self.bulk_attachments = bulk_attachments
        self.copy_assets = copy_assets
        self.log_callback = log_callback or (lambda msg: None)
        self.progress_callback = progress_callback or (lambda cur, tot, name: None)

    def log(self, msg: str):
        self.log_callback(msg)

    def convert(self) -> Dict[str, Any]:
        """
        Executes conversion for all queued items.
        """
        total = len(self.items)
        overall_report: Dict[str, Any] = {
            "total_items": total,
            "successful_items": 0,
            "failed_items": 0,
            "total_weapons": 0,
            "total_attachments": 0,
            "item_reports": [],
            "errors": []
        }

        self.log(f"[*] Starting batch conversion of {total} item(s)...")

        for idx, item in enumerate(self.items, 1):
            item_name = item.name
            self.progress_callback(idx, total, item_name)
            self.log(f"\n[{idx}/{total}] Processing: {item_name}")

            if not item.exists():
                err = f"Item does not exist: {item}"
                self.log(f"  [ERROR] {err}")
                overall_report["failed_items"] += 1
                overall_report["errors"].append(err)
                continue

            try:
                # Case 1: Directory Addon
                if item.is_dir():
                    if self.output_parent_dir:
                        out_name = re.sub(r'^arccw_', 'arc9_', item_name, flags=re.IGNORECASE)
                        if out_name == item_name:
                            out_name = f"arc9_{item_name}"
                        out_dir = self.output_parent_dir / out_name
                    else:
                        out_dir = None

                    conv = AddonConverter(
                        input_dir=item,
                        output_dir=out_dir,
                        bulk_attachments=self.bulk_attachments,
                        copy_assets=self.copy_assets
                    )
                    rep = conv.convert()
                    weapons_count = len(rep["weapons"])
                    atts_count = len(rep["attachments"])
                    overall_report["total_weapons"] += weapons_count
                    overall_report["total_attachments"] += atts_count
                    overall_report["successful_items"] += 1

                    self.log(f"  [+] Addon converted to: {conv.output_dir.name}")
                    self.log(f"      Weapons: {weapons_count}, Attachments: {atts_count}, Asset folders: {', '.join(rep['copied_dirs']) or 'None'}")
                    if rep["warnings"]:
                        for w in rep["warnings"]:
                            self.log(f"      [!] Warning: {w}")

                    overall_report["item_reports"].append({
                        "name": item_name,
                        "destination": str(conv.output_dir),
                        "status": "success",
                        "report": rep
                    })

                # Case 2: Single file
                elif item.is_file():
                    content = item.read_text(encoding="utf-8", errors="replace")
                    is_att = "att.PrintName" in content or "att.Slot" in content or "attachments" in str(item).lower()

                    if is_att:
                        ac = AttachmentConverter(content, att_id=item.stem)
                        res = ac.convert(is_bulk=False)
                        out_name = f"arc9_{item.name}"
                        out_file = (self.output_parent_dir / out_name) if self.output_parent_dir else (item.parent / out_name)
                        out_file.write_text(res, encoding="utf-8")
                        overall_report["total_attachments"] += 1
                        self.log(f"  [+] Converted attachment saved to: {out_file.name}")
                    else:
                        wc = WeaponConverter(content, filename=item.name)
                        res = wc.convert()
                        out_name = item.name.replace("arccw_", "arc9_")
                        if out_name == item.name:
                            out_name = f"arc9_{item.name}"
                        out_file = (self.output_parent_dir / out_name) if self.output_parent_dir else (item.parent / out_name)
                        out_file.write_text(res, encoding="utf-8")
                        overall_report["total_weapons"] += 1
                        self.log(f"  [+] Converted weapon saved to: {out_file.name}")

                    overall_report["successful_items"] += 1
                    overall_report["item_reports"].append({
                        "name": item_name,
                        "destination": str(out_file),
                        "status": "success"
                    })

            except Exception as e:
                err = f"Failed to convert {item_name}: {e}"
                self.log(f"  [ERROR] {err}")
                overall_report["failed_items"] += 1
                overall_report["errors"].append(err)
                overall_report["item_reports"].append({
                    "name": item_name,
                    "status": "failed",
                    "error": str(e)
                })

        self.log("\n==========================================")
        self.log(f"[SUCCESS] Batch conversion finished.")
        self.log(f"Items processed: {overall_report['successful_items']} succeeded, {overall_report['failed_items']} failed")
        self.log(f"Total weapons converted: {overall_report['total_weapons']}")
        self.log(f"Total attachments converted: {overall_report['total_attachments']}")
        self.log("==========================================\n")

        return overall_report
