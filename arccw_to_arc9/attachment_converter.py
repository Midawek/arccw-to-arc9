"""
ArcCW to ARC9 Attachment Converter
Converts ArcCW attachment files into ARC9 attachments.
Can output individual attachment files or a single bulk attachment file.
"""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from .lua_parser import LuaParser
from .lua_ast import (
    LuaValue, LuaNil, LuaBool, LuaNumber, LuaString,
    LuaVector, LuaAngle, LuaColor, LuaMaterial, LuaRaw,
    LuaTable, LuaTableEntry
)

class AttachmentConverter:
    # Direct mapping for multipliers: Mult_X -> ARC9 property
    MULT_MAP = {
        "Mult_Recoil": "RecoilMult",
        "Mult_RecoilSide": "RecoilSideMult",
        "Mult_RecoilRise": "RecoilUpMult",
        "Mult_VisualRecoil": "VisualRecoilMult",
        "Mult_SightTime": "AimDownSightsTimeMult",
        "Mult_MoveSpeed": "SpeedMult",
        "Mult_SightedSpeedMult": "SpeedMultSights",
        "Mult_AccuracyMOA": "SpreadMult",
        "Mult_HipDispersion": "SpreadMultHipFire",
        "Mult_MoveDispersion": "SpreadMultMove",
        "Mult_SightsDispersion": "SpreadMultSights",
        "Mult_RPM": "RPMMult",
        "Mult_ReloadTime": "ReloadTimeMult",
        "Mult_DrawTime": "DeployTimeMult",
        "Mult_ShootPitch": "ShootPitchMult",
        "Mult_Penetration": "PenetrationMult",
        "Mult_MuzzleVelocity": "PhysBulletMuzzleVelocityMult",
        "Mult_DamageMin": "DamageMinMult",
        "Mult_ClipSize": "ClipSizeMult",
    }

    ADD_MAP = {
        "Add_Recoil": "RecoilAdd",
        "Add_RecoilSide": "RecoilSideAdd",
        "Add_RecoilRise": "RecoilUpAdd",
        "Add_SightTime": "AimDownSightsTimeAdd",
        "Add_DamageMin": "DamageMinAdd",
        "Add_Penetration": "PenetrationAdd",
        "Add_ClipSize": "ClipSizeAdd",
        "Add_RPM": "RPMAdd",
    }

    OVERRIDE_MAP = {
        "Override_BodyDamageMults": "BodyDamageMultsOverride",
        "Override_DamageMin": "DamageMinOverride",
        "Override_Penetration": "PenetrationOverride",
        "Override_Ammo": "AmmoOverride",
        "Override_ClipSize": "ClipSizeOverride",
        "Override_RPM": "RPMOverride",
        "Override_ShootSound": "ShootSoundOverride",
        "Override_ShootSoundSilenced": "ShootSoundSilencedOverride",
        "Override_MuzzleEffect": "MuzzleParticleOverride",
        "Override_Tracer": "TracerEffectOverride",
    }

    def __init__(self, content: str, att_id: str):
        self.raw_content = content
        self.att_id = att_id
        self.parser = LuaParser(content)
        self.statements, self.stat_map = self.parser.parse()

    def convert(self, is_bulk: bool = False) -> str:
        """Converts to ARC9 attachment Lua code"""
        lines: List[str] = []

        if is_bulk:
            lines.append("--------------------------------------------------------------------------------")
            lines.append("ATT = {}")
        else:
            lines.append("local ATT = {}")

        # Identity
        print_name = self._get_stat(["att.PrintName", "ATT.PrintName"])
        if print_name:
            lines.append(f'ATT.PrintName = {print_name.to_lua()}')
        else:
            # Fallback title from att_id
            name_fallback = self.att_id.replace("_", " ").title()
            lines.append(f'ATT.PrintName = "{name_fallback}"')

        desc = self._get_stat(["att.Description", "ATT.Description"])
        if desc:
            lines.append(f'ATT.Description = {desc.to_lua()}')

        icon = self._get_stat(["att.Icon", "ATT.Icon"])
        if icon:
            lines.append(f'ATT.Icon = {icon.to_lua()}')

        sort_order = self._get_stat(["att.SortOrder", "ATT.SortOrder"])
        if sort_order:
            lines.append(f'ATT.SortOrder = {sort_order.to_lua()}')

        auto_stats = self._get_stat(["att.AutoStats", "ATT.AutoStats"])
        if auto_stats:
            lines.append(f'ATT.AutoStats = {auto_stats.to_lua()}')

        free = self._get_stat(["att.Free", "ATT.Free"])
        if free:
            lines.append(f'ATT.Free = {free.to_lua()}')

        # Category / Slot
        slot = self._get_stat(["att.Slot", "ATT.Category", "att.Category"])
        if slot:
            if isinstance(slot, LuaString):
                lines.append(f'ATT.Category = "{slot.value}"')
            else:
                lines.append(f'ATT.Category = {slot.to_lua()}')

        # Automatically link ActivateElements to matching element
        activate_elements = self._get_stat(["att.ActivateElements", "ATT.ActivateElements"])
        if activate_elements:
            lines.append(f'ATT.ActivateElements = {activate_elements.to_lua()}')
        else:
            # Default to activating an element named after att_id
            lines.append(f'ATT.ActivateElements = {{"{self.att_id}"}}')

        # Model & Offsets
        model = self._get_stat(["att.Model", "ATT.Model"])
        if model:
            lines.append(f'ATT.Model = {model.to_lua()}')
        model_offset = self._get_stat(["att.ModelOffset", "ATT.ModelOffset"])
        if model_offset:
            lines.append(f'ATT.ModelOffset = {model_offset.to_lua()}')
        model_ang = self._get_stat(["att.ModelAngleOffset", "ATT.ModelAngleOffset"])
        if model_ang:
            lines.append(f'ATT.ModelAngleOffset = {model_ang.to_lua()}')
        scale = self._get_stat(["att.Scale", "ATT.Scale"])
        if scale:
            lines.append(f'ATT.Scale = {scale.to_lua()}')

        # Silencer / Muzzle
        silencer = self._get_stat(["att.Silencer", "ATT.Silencer"])
        if silencer:
            lines.append(f'ATT.Silencer = {silencer.to_lua()}')
        muzzle_dev = self._get_stat(["att.MuzzleDevice", "ATT.MuzzleDevice"])
        if muzzle_dev:
            lines.append(f'ATT.MuzzleDevice = {muzzle_dev.to_lua()}')
        muzzle_prio = self._get_stat(["att.MuzzleDevice_Priority", "ATT.MuzzleDevice_Priority"])
        if muzzle_prio:
            lines.append(f'ATT.MuzzleDevice_Priority = {muzzle_prio.to_lua()}')

        # LHIK
        lhik = self._get_stat(["att.LHIK", "ATT.LHIK"])
        if lhik:
            lines.append(f'ATT.LHIK = {lhik.to_lua()}')
        lhik_prio = self._get_stat(["att.LHIK_Priority", "ATT.LHIK_Priority"])
        if lhik_prio:
            lines.append(f'ATT.LHIK_Priority = {lhik_prio.to_lua()}')

        # Stats: Mult
        for k, arc9_k in self.MULT_MAP.items():
            val = self._get_stat([f"att.{k}", f"ATT.{arc9_k}"])
            if val:
                lines.append(f'ATT.{arc9_k} = {val.to_lua()}')

        # Special Mult_Range -> RangeMaxMult & RangeMinMult
        mult_range = self._get_stat(["att.Mult_Range", "ATT.RangeMaxMult"])
        if mult_range:
            lines.append(f'ATT.RangeMaxMult = {mult_range.to_lua()}')
            lines.append(f'ATT.RangeMinMult = {mult_range.to_lua()}')

        # Special Mult_Damage -> DamageMaxMult & DamageMinMult
        mult_dmg = self._get_stat(["att.Mult_Damage", "ATT.DamageMaxMult"])
        if mult_dmg:
            lines.append(f'ATT.DamageMaxMult = {mult_dmg.to_lua()}')
            lines.append(f'ATT.DamageMinMult = {mult_dmg.to_lua()}')

        # Stats: Add
        for k, arc9_k in self.ADD_MAP.items():
            val = self._get_stat([f"att.{k}", f"ATT.{arc9_k}"])
            if val:
                lines.append(f'ATT.{arc9_k} = {val.to_lua()}')

        add_dmg = self._get_stat(["att.Add_Damage", "ATT.DamageMaxAdd"])
        if add_dmg:
            lines.append(f'ATT.DamageMaxAdd = {add_dmg.to_lua()}')
            lines.append(f'ATT.DamageMinAdd = {add_dmg.to_lua()}')

        # Stats: Override
        for k, arc9_k in self.OVERRIDE_MAP.items():
            val = self._get_stat([f"att.{k}", f"ATT.{arc9_k}"])
            if val:
                lines.append(f'ATT.{arc9_k} = {val.to_lua()}')

        over_dmg = self._get_stat(["att.Override_Damage", "ATT.DamageMaxOverride"])
        if over_dmg:
            lines.append(f'ATT.DamageMaxOverride = {over_dmg.to_lua()}')
            lines.append(f'ATT.DamageMinOverride = {over_dmg.to_lua()}')

        over_range = self._get_stat(["att.Override_Range", "ATT.RangeMaxOverride"])
        if over_range:
            lines.append(f'ATT.RangeMaxOverride = {over_range.to_lua()} / ARC9.HUToM')

        over_phys = self._get_stat(["att.Override_PhysBulletMuzzleVelocity", "ATT.PhysBulletMuzzleVelocityOverride"])
        if over_phys:
            lines.append(f'ATT.PhysBulletMuzzleVelocityOverride = {over_phys.to_lua()} / ARC9.HUToM')

        # Emit helper locals and helper functions (e.g. local Distance = ..., local function FindTarget)
        for stmt in self.statements:
            if stmt["type"] == "raw" and "local " in stmt.get("code", ""):
                code = self._adapt_custom_lua(stmt["code"])
                lines.append(code)
            elif stmt.get("is_local") and stmt.get("target") and stmt.get("value"):
                code = f"local {stmt['target']} = {stmt['value'].to_lua()}"
                lines.append(self._adapt_custom_lua(code))
            elif stmt["type"] == "function":
                code = self._adapt_custom_lua(stmt["code"])
                lines.append(code)

        # Custom functions: Hook_*, DrawFunc, etc.
        for stmt in self.statements:
            if stmt["type"] == "assignment":
                target = stmt["target"]
                if target in ("att.DrawFunc", "ATT.DrawFunc"):
                    code = stmt["value"].to_lua()
                    lines.append(f"ATT.DrawFunc = {self._adapt_custom_lua(code)}")
                elif target and (target.startswith("att.Hook_") or target.startswith("ATT.Hook_")):
                    new_target = re.sub(r'^att\.', 'ATT.', target)
                    code = stmt["value"].to_lua()
                    lines.append(f"{new_target} = {self._adapt_custom_lua(code)}")

        # Final loader
        lines.append(f'ARC9.LoadAttachment(ATT, "{self.att_id}")\n')
        return "\n".join(lines)

    def _adapt_custom_lua(self, code: str) -> str:
        code = re.sub(r'\batt\.', 'ATT.', code)
        code = re.sub(r'\bArcCW\.STATE_SIGHTS\b', '(wep.GetInSights and wep:GetInSights() or false)', code)
        code = re.sub(r'\bArcCW\.STATE_SPRINT\b', '(wep.GetSprintAmount and wep:GetSprintAmount() > 0 or false)', code)
        code = re.sub(r'\bArcCW\b', 'ARC9', code)
        return code

    def _get_stat(self, keys: List[str]) -> Optional[LuaValue]:
        for k in keys:
            v = self.stat_map.get(k)
            if v is not None:
                return v
        return None
