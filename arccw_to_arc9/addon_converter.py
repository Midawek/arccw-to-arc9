"""
Full Addon Converter for ArcCW to ARC9
Handles complete Garry's Mod addon directory structure conversion:
- Weapons: lua/weapons/arccw_* -> lua/weapons/arc9_*
- Attachments: lua/arccw/.../attachments -> lua/arc9/common/attachments_bulk/ or attachments/
- Shared / Autorun: soundscripts, particles, ammo
- Assets: models, materials (with spawnmenu icons mapped), sound, particles
- Metadata: addon.json title and tags
"""
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .weapon_converter import WeaponConverter
from .attachment_converter import AttachmentConverter

class AddonConverter:
    def __init__(self, input_dir: Union[str, Path], output_dir: Optional[Union[str, Path]] = None, bulk_attachments: bool = True, copy_assets: bool = True):
        self.input_dir = Path(input_dir).resolve()
        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            # Generate output dir name: arccw_xxx -> arc9_xxx
            in_name = self.input_dir.name
            out_name = re.sub(r'^arccw_', 'arc9_', in_name, flags=re.IGNORECASE)
            if out_name == in_name:
                out_name = f"arc9_{in_name}"
            self.output_dir = self.input_dir.parent / out_name

        self.bulk_attachments = bulk_attachments
        self.copy_assets = copy_assets
        self.report: Dict[str, Any] = {
            "weapons": [],
            "attachments": [],
            "copied_dirs": [],
            "warnings": []
        }

    def convert(self) -> Dict[str, Any]:
        """Performs full conversion and returns a summary report"""
        if not self.input_dir.exists() or not self.input_dir.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {self.input_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Convert addon.json if present
        self._convert_addon_json()

        # 2. Copy asset folders: materials, models, sound, particles
        if self.copy_assets:
            self._copy_assets()

        # 3. Convert Weapons in lua/weapons/
        self._convert_weapons()

        # 4. Convert Attachments in lua/arccw/...
        self._convert_attachments()

        # 5. Convert / Copy other lua scripts (autorun, shared)
        self._convert_other_lua()

        # 6. Check and alias spawnmenu icons if needed
        if self.copy_assets:
            self._alias_spawnmenu_icons()

        return self.report

    def _convert_addon_json(self):
        addon_json_path = self.input_dir / "addon.json"
        if not addon_json_path.exists():
            return

        try:
            with open(addon_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "title" in data:
                # Replace ArcCW with ARC9
                data["title"] = re.sub(r'\bArcCW\b', 'ARC9', data["title"], flags=re.IGNORECASE)

            # Ensure type is weapon
            data["type"] = data.get("type", "weapon")

            out_addon_json = self.output_dir / "addon.json"
            with open(out_addon_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            self.report["warnings"].append(f"Failed to process addon.json: {e}")

    def _copy_assets(self):
        asset_dirs = ["materials", "models", "sound", "particles"]
        for adir in asset_dirs:
            src = self.input_dir / adir
            if src.exists() and src.is_dir():
                dst = self.output_dir / adir
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                self.report["copied_dirs"].append(adir)

    def _convert_weapons(self):
        weapons_dir = self.input_dir / "lua" / "weapons"
        if not weapons_dir.exists():
            return

        out_weapons_dir = self.output_dir / "lua" / "weapons"
        out_weapons_dir.mkdir(parents=True, exist_ok=True)

        # Process single-file SWEPs: arccw_*.lua
        for item in weapons_dir.iterdir():
            if item.is_file() and item.suffix == ".lua":
                new_filename = self._map_weapon_filename(item.name)
                try:
                    content = item.read_text(encoding="utf-8", errors="replace")
                    wc = WeaponConverter(content, filename=item.name)
                    converted_code = wc.convert()

                    out_file = out_weapons_dir / new_filename
                    out_file.write_text(converted_code, encoding="utf-8")
                    self.report["weapons"].append({
                        "source": item.name,
                        "destination": new_filename,
                        "status": "success"
                    })
                except Exception as e:
                    self.report["warnings"].append(f"Error converting weapon {item.name}: {e}")

            # Process folder SWEPs: arccw_xxx/shared.lua
            elif item.is_dir():
                new_dir_name = self._map_weapon_filename(item.name)
                out_wep_folder = out_weapons_dir / new_dir_name
                out_wep_folder.mkdir(parents=True, exist_ok=True)

                shared_file = item / "shared.lua"
                if shared_file.exists():
                    try:
                        content = shared_file.read_text(encoding="utf-8", errors="replace")
                        wc = WeaponConverter(content, filename=shared_file.name)
                        converted_code = wc.convert()

                        out_shared = out_wep_folder / "shared.lua"
                        out_shared.write_text(converted_code, encoding="utf-8")
                        self.report["weapons"].append({
                            "source": f"{item.name}/shared.lua",
                            "destination": f"{new_dir_name}/shared.lua",
                            "status": "success"
                        })
                    except Exception as e:
                        self.report["warnings"].append(f"Error converting weapon {item.name}/shared.lua: {e}")

                # Copy other files in the folder (cl_init.lua, init.lua)
                for sub in item.iterdir():
                    if sub.name != "shared.lua" and sub.is_file():
                        shutil.copy2(sub, out_wep_folder / sub.name)

    def _convert_attachments(self):
        # Look for attachments in lua/arccw/**/attachments/
        att_dirs: List[Path] = []
        for root, dirs, files in os.walk(self.input_dir / "lua"):
            if self.output_dir in Path(root).parents or Path(root) == self.output_dir:
                continue
            if "attachments" in dirs:
                att_dirs.append(Path(root) / "attachments")

        found_att_files: List[Path] = []
        for ad in att_dirs:
            for f in ad.glob("*.lua"):
                found_att_files.append(f)

        if not found_att_files:
            return

        pack_name = self.output_dir.name.replace("arc9_", "").replace("arccw_", "")

        if self.bulk_attachments:
            # Write all attachments into a single bulk file: lua/arc9/common/attachments_bulk/arc9_<pack>_attachs.lua
            bulk_dir = self.output_dir / "lua" / "arc9" / "common" / "attachments_bulk"
            bulk_dir.mkdir(parents=True, exist_ok=True)
            bulk_filename = f"arc9_{pack_name}_attachs.lua"
            bulk_file = bulk_dir / bulk_filename

            bulk_lines: List[str] = [
                f"-- ARC9 Bulk Attachments for {pack_name.title()}",
                "-- Auto-generated by ArcCW to ARC9 Converter",
                ""
            ]

            for att_path in found_att_files:
                att_id = att_path.stem
                try:
                    content = att_path.read_text(encoding="utf-8", errors="replace")
                    ac = AttachmentConverter(content, att_id)
                    conv_code = ac.convert(is_bulk=True)
                    bulk_lines.append(conv_code)
                    self.report["attachments"].append({
                        "source": att_path.name,
                        "att_id": att_id,
                        "mode": "bulk",
                        "status": "success"
                    })
                except Exception as e:
                    self.report["warnings"].append(f"Error converting attachment {att_path.name}: {e}")

            bulk_file.write_text("\n".join(bulk_lines), encoding="utf-8")

        else:
            # Write separate files in lua/arc9/common/attachments/
            single_dir = self.output_dir / "lua" / "arc9" / "common" / "attachments"
            single_dir.mkdir(parents=True, exist_ok=True)

            for att_path in found_att_files:
                att_id = att_path.stem
                try:
                    content = att_path.read_text(encoding="utf-8", errors="replace")
                    ac = AttachmentConverter(content, att_id)
                    conv_code = ac.convert(is_bulk=False)
                    out_f = single_dir / f"{att_id}.lua"
                    out_f.write_text(conv_code, encoding="utf-8")
                    self.report["attachments"].append({
                        "source": att_path.name,
                        "att_id": att_id,
                        "mode": "single",
                        "status": "success"
                    })
                except Exception as e:
                    self.report["warnings"].append(f"Error converting attachment {att_path.name}: {e}")

    def _convert_other_lua(self):
        # 1. Autorun soundscripts or init
        autorun_dir = self.input_dir / "lua" / "autorun"
        if autorun_dir.exists():
            out_autorun = self.output_dir / "lua" / "autorun"
            out_autorun.mkdir(parents=True, exist_ok=True)
            for item in autorun_dir.iterdir():
                if item.is_file() and item.suffix == ".lua":
                    content = item.read_text(encoding="utf-8", errors="replace")
                    content = re.sub(r'\bArcCW\b', 'ARC9', content)
                    (out_autorun / item.name).write_text(content, encoding="utf-8")
                elif item.is_file():
                    shutil.copy2(item, out_autorun / item.name)

        # 2. lua/effects/ (custom muzzle flashes, tracers, impacts)
        effects_dir = self.input_dir / "lua" / "effects"
        if effects_dir.exists():
            out_effects = self.output_dir / "lua" / "effects"
            out_effects.mkdir(parents=True, exist_ok=True)
            for root, dirs, files in os.walk(effects_dir):
                if self.output_dir in Path(root).parents or Path(root) == self.output_dir:
                    continue
                rel = Path(root).relative_to(effects_dir)
                target_dir = out_effects / rel
                target_dir.mkdir(parents=True, exist_ok=True)
                for f in files:
                    src_f = Path(root) / f
                    dst_f = target_dir / f
                    if src_f.suffix == ".lua":
                        content = src_f.read_text(encoding="utf-8", errors="replace")
                        content = re.sub(r'\bArcCW\b', 'ARC9', content)
                        dst_f.write_text(content, encoding="utf-8")
                    else:
                        shutil.copy2(src_f, dst_f)

        # 3. lua/entities/
        entities_dir = self.input_dir / "lua" / "entities"
        if entities_dir.exists():
            out_entities = self.output_dir / "lua" / "entities"
            out_entities.mkdir(parents=True, exist_ok=True)
            for root, dirs, files in os.walk(entities_dir):
                if self.output_dir in Path(root).parents or Path(root) == self.output_dir:
                    continue
                rel = Path(root).relative_to(entities_dir)
                target_dir = out_entities / rel
                target_dir.mkdir(parents=True, exist_ok=True)
                for f in files:
                    src_f = Path(root) / f
                    dst_f = target_dir / f
                    if src_f.suffix == ".lua":
                        content = src_f.read_text(encoding="utf-8", errors="replace")
                        content = re.sub(r'\bArcCW\b', 'ARC9', content)
                        dst_f.write_text(content, encoding="utf-8")
                    else:
                        shutil.copy2(src_f, dst_f)

        # 4. lua/arccw/** (shared sounds, effects, ammo - excluding attachments)
        arccw_dir = self.input_dir / "lua" / "arccw"
        if arccw_dir.exists():
            out_arc9_shared = self.output_dir / "lua" / "arc9" / "shared"
            out_arc9_shared.mkdir(parents=True, exist_ok=True)

            for root, dirs, files in os.walk(arccw_dir):
                if self.output_dir in Path(root).parents or Path(root) == self.output_dir:
                    continue
                if "attachments" in Path(root).parts:
                    continue
                for f in files:
                    if f.endswith(".lua"):
                        src_f = Path(root) / f
                        content = src_f.read_text(encoding="utf-8", errors="replace")
                        content = re.sub(r'\bArcCW\b', 'ARC9', content)
                        (out_arc9_shared / f).write_text(content, encoding="utf-8")

    def _alias_spawnmenu_icons(self):
        # Look for materials/entities/arccw_*.png or .vmt
        ent_dir = self.output_dir / "materials" / "entities"
        if not ent_dir.exists():
            return

        for wep in self.report["weapons"]:
            src_wep = Path(wep["source"]).stem
            dst_wep = Path(wep["destination"]).stem
            if src_wep != dst_wep:
                # Check for png / vtf / vmt icons
                for ext in [".png", ".vmt", ".vtf"]:
                    icon_src = ent_dir / f"{src_wep}{ext}"
                    icon_dst = ent_dir / f"{dst_wep}{ext}"
                    if icon_src.exists() and not icon_dst.exists():
                        shutil.copy2(icon_src, icon_dst)

    def _map_weapon_filename(self, name: str) -> str:
        new_name = re.sub(r'^arccw_', 'arc9_', name, flags=re.IGNORECASE)
        if new_name == name:
            new_name = f"arc9_{name}"
        return new_name
