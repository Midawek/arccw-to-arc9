"""
ArcCW to ARC9 Weapon Converter
Converts SWEP Lua files from Arctic's Customizable Weapons to ARC9.
"""
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from .lua_parser import LuaParser
from .lua_ast import (
    LuaValue, LuaNil, LuaBool, LuaNumber, LuaString,
    LuaVector, LuaAngle, LuaColor, LuaMaterial, LuaRaw,
    LuaTable, LuaTableEntry
)

class WeaponConverter:
    def __init__(self, content: str, filename: str = "arccw_weapon.lua"):
        self.raw_content = content
        self.filename = filename
        self.parser = LuaParser(content)
        self.statements, self.stat_map = self.parser.parse()

    def convert(self) -> str:
        """Converts the weapon to ARC9 Lua code string"""
        out_lines: List[str] = []

        # 1. Base Class & Categories
        out_lines.append('SWEP.Base = "arc9_base"')
        out_lines.append('SWEP.Spawnable = true')
        out_lines.append('SWEP.NotForNPCs = false')

        category = self._get_str("SWEP.Category", "ARC9")
        # Replace ArcCW with ARC9 in category
        category = re.sub(r'\bArcCW\b', 'ARC9', category)
        out_lines.append(f'SWEP.Category = "{category}"')

        subcat = self._get_str("SWEP.SubCategory")
        if subcat:
            out_lines.append(f'SWEP.SubCategory = "{subcat}"')

        admin_only = self._get_bool("SWEP.AdminOnly", False)
        if admin_only:
            out_lines.append('SWEP.AdminOnly = true')

        # PrintName & Trivia
        print_name = self._get_str("SWEP.PrintName", self._get_str("SWEP.TrueName", "Weapon"))
        out_lines.append(f'SWEP.PrintName = "{print_name}"')
        true_name = self._get_str("SWEP.TrueName")
        if true_name and true_name != print_name:
            out_lines.append(f'SWEP.TrueName = "{true_name}"')

        wep_class = self._get_str("SWEP.Trivia_Class", self._get_str("SWEP.Class", "Firearm"))
        out_lines.append(f'SWEP.Class = "{wep_class}"')

        # Trivia table
        trivia_entries = []
        country = self._get_str("SWEP.Trivia_Country")
        if country:
            trivia_entries.append(f'    ["Country of Origin"] = "{country}",')
        mfg = self._get_str("SWEP.Trivia_Manufacturer")
        if mfg:
            trivia_entries.append(f'    ["Manufacturer"] = "{mfg}",')
        cal = self._get_str("SWEP.Trivia_Calibre", self._get_str("SWEP.Trivia_Caliber"))
        if cal:
            trivia_entries.append(f'    ["Caliber"] = "{cal}",')
        mech = self._get_str("SWEP.Trivia_Mechanism")
        if mech:
            trivia_entries.append(f'    ["Mechanism"] = "{mech}",')
        year = self.stat_map.get("SWEP.Trivia_Year")
        if year:
            trivia_entries.append(f'    ["Year"] = {year.to_lua()},')

        if trivia_entries:
            out_lines.append('SWEP.Trivia = {')
            out_lines.extend(trivia_entries)
            out_lines.append('}')

        desc = self._get_str("SWEP.Trivia_Desc", self._get_str("SWEP.Description"))
        if desc:
            # Escape or format as multiline
            desc_clean = desc.replace(']]', '] ]')
            out_lines.append(f'SWEP.Description = [[{desc_clean}]]')

        # Models & Slots
        vm = self._get_str("SWEP.ViewModel", "models/weapons/v_pistol.mdl")
        wm = self._get_str("SWEP.WorldModel", "models/weapons/w_pistol.mdl")
        out_lines.append(f'SWEP.ViewModel = "{vm}"')
        out_lines.append(f'SWEP.WorldModel = "{wm}"')

        slot = self.stat_map.get("SWEP.Slot")
        if slot:
            out_lines.append(f'SWEP.Slot = {slot.to_lua()}')
        slot_pos = self.stat_map.get("SWEP.SlotPos")
        if slot_pos:
            out_lines.append(f'SWEP.SlotPos = {slot_pos.to_lua()}')

        if self._get_bool("SWEP.MirrorVMWM", False):
            out_lines.append('SWEP.MirrorVMWM = true')
            mwm = self._get_str("SWEP.MirrorWorldModel", vm)
            out_lines.append(f'SWEP.WorldModelMirror = "{mwm}"')

        # WorldModelOffset
        wm_offset = self.stat_map.get("SWEP.WorldModelOffset")
        if isinstance(wm_offset, LuaTable):
            out_lines.append('SWEP.WorldModelOffset = {')
            pos = wm_offset.get("pos", wm_offset.get("Pos"))
            ang = wm_offset.get("ang", wm_offset.get("Ang"))
            scale = wm_offset.get("scale", wm_offset.get("Scale"))
            if pos:
                out_lines.append(f'    Pos = {pos.to_lua()},')
            if ang:
                out_lines.append(f'    Ang = {ang.to_lua()},')
            # Third-person IK support
            if pos:
                out_lines.append(f'    TPIKPos = {pos.to_lua()},')
            if ang:
                out_lines.append(f'    TPIKAng = {ang.to_lua()},')
            if scale:
                out_lines.append(f'    Scale = {scale.to_lua()},')
            out_lines.append('}')

        # 2. Damage Profile
        out_lines.append('\n-------------------------- DAMAGE PROFILE')
        dmg = self._get_num("SWEP.Damage", 30)
        dmg_min = self._get_num("SWEP.DamageMin", dmg * 0.6)
        out_lines.append(f'SWEP.DamageMax = {self._fmt_num(dmg)}')
        out_lines.append(f'SWEP.DamageMin = {self._fmt_num(dmg_min)}')

        range_val = self._get_num("SWEP.Range", 50)
        range_min = self._get_num("SWEP.RangeMin", range_val * 0.3)
        out_lines.append(f'SWEP.RangeMin = {self._fmt_num(range_min)} / ARC9.HUToM')
        out_lines.append(f'SWEP.RangeMax = {self._fmt_num(range_val)} / ARC9.HUToM')

        pen = self._get_num("SWEP.Penetration", 8)
        out_lines.append(f'SWEP.Penetration = {self._fmt_num(pen)}')

        dmg_type = self.stat_map.get("SWEP.DamageType")
        if dmg_type:
            out_lines.append(f'SWEP.DamageType = {dmg_type.to_lua()}')

        force = self._get_num("SWEP.Force")
        if force is not None:
            out_lines.append(f'SWEP.ImpactForce = {self._fmt_num(force)}')

        body_mults = self.stat_map.get("SWEP.BodyDamageMults")
        if isinstance(body_mults, LuaTable):
            out_lines.append(f'SWEP.BodyDamageMults = {body_mults.to_lua(0)}')

        # 3. Phys Bullet Ballistics
        out_lines.append('\n-------------------------- PHYS BULLET BALLISTICS')
        phys_vel = self._get_num("SWEP.PhysBulletMuzzleVelocity", self._get_num("SWEP.MuzzleVelocity", 750))
        out_lines.append(f'SWEP.PhysBulletMuzzleVelocity = {self._fmt_num(phys_vel)} / ARC9.HUToM')
        out_lines.append('SWEP.PhysBulletGravity = 1.5')
        out_lines.append('SWEP.PhysBulletDrag = 1.15')

        # 4. Magazine & Ammo
        out_lines.append('\n-------------------------- MAGAZINE')
        ammo = self._get_str("SWEP.Primary.Ammo", self._get_str("SWEP.Ammo", "pistol"))
        clip = self._get_num("SWEP.Primary.ClipSize", self._get_num("SWEP.ClipSize", 10))
        chamber = self._get_num("SWEP.ChamberSize", 1)
        out_lines.append(f'SWEP.Ammo = "{ammo}"')
        out_lines.append(f'SWEP.ClipSize = {int(clip)}')
        out_lines.append(f'SWEP.ChamberSize = {int(chamber)}')
        out_lines.append('SWEP.SupplyLimit = 6')
        out_lines.append('SWEP.SecondarySupplyLimit = 10')
        out_lines.append('SWEP.DrawCrosshair = true')
        out_lines.append('SWEP.Crosshair = true')

        # Shotgun reload
        is_shotgun = self._get_bool("SWEP.ShotgunReload", False)
        if not is_shotgun:
            animations = self.stat_map.get("SWEP.Animations")
            if isinstance(animations, LuaTable):
                for e in animations.entries:
                    k = e.key.value if isinstance(e.key, LuaString) else str(e.key)
                    if k.startswith("sgreload") or k == "reload_insert":
                        is_shotgun = True
                        break

        if is_shotgun:
            out_lines.append('\n-------------------------- SHOTGUN RELOAD')
            out_lines.append('SWEP.ShotgunReload = true')
            custom_inc = self.stat_map.get("SWEP.ShotgunReloadIncludesChamber")
            if isinstance(custom_inc, LuaBool):
                out_lines.append(f'SWEP.ShotgunReloadIncludesChamber = {"true" if custom_inc.value else "false"}')
            else:
                out_lines.append(f'SWEP.ShotgunReloadIncludesChamber = {"true" if chamber > 0 else "false"}')

        # 5. Fire Rate & Firemodes
        out_lines.append('\n-------------------------- FIREMODES')
        delay = self._get_num("SWEP.Delay")
        rpm = self._get_num("SWEP.RPM")
        if rpm:
            out_lines.append(f'SWEP.RPM = {int(rpm)}')
        elif delay and delay > 0:
            calc_rpm = round(60.0 / delay)
            out_lines.append(f'SWEP.RPM = {calc_rpm}')
        else:
            out_lines.append('SWEP.RPM = 600')

        num_shots = self._get_num("SWEP.Num", 1)
        if num_shots > 1:
            out_lines.append(f'SWEP.Num = {int(num_shots)}')

        # Firemodes table conversion
        firemodes = self.stat_map.get("SWEP.Firemodes")
        if isinstance(firemodes, LuaTable):
            converted_modes = self._convert_firemodes(firemodes)
            out_lines.append(f'SWEP.Firemodes = {converted_modes.to_lua(0)}')
        else:
            # Default auto & semi
            out_lines.append('''SWEP.Firemodes = {
    { Mode = -1 },
    { Mode = 1 }
}''')

        # 6. Recoil
        out_lines.append('\n-------------------------- RECOIL')
        recoil = self._get_num("SWEP.Recoil", 1)
        recoil_side = self._get_num("SWEP.RecoilSide", 0.1)
        recoil_rise = self._get_num("SWEP.RecoilRise", 0.5)
        recoil_punch = self._get_num("SWEP.RecoilPunch", 2)
        vis_mult = self._get_num("SWEP.VisualRecoilMult", 1)

        out_lines.append(f'SWEP.Recoil = {self._fmt_num(recoil)}')
        out_lines.append(f'SWEP.RecoilUp = {self._fmt_num(recoil_rise)}')
        out_lines.append(f'SWEP.RecoilSide = {self._fmt_num(recoil_side)}')
        out_lines.append(f'SWEP.RecoilKick = {self._fmt_num(recoil_punch)}')
        out_lines.append(f'SWEP.VisualRecoilMult = {self._fmt_num(vis_mult)}')
        out_lines.append('SWEP.RecoilAutoControl = 0.5')
        out_lines.append('SWEP.RecoilDissipationRate = 10')
        out_lines.append('SWEP.RecoilResetTime = 0.05')

        # 7. Spread / Accuracy
        out_lines.append('\n-------------------------- SPREAD')
        moa = self._get_num("SWEP.AccuracyMOA", 5)
        hip_disp = self._get_num("SWEP.HipDispersion", 30)
        move_disp = self._get_num("SWEP.MoveDispersion", 40)
        sight_disp = self._get_num("SWEP.SightsDispersion", 0)
        jump_disp = self._get_num("SWEP.JumpDispersion", 60)

        out_lines.append(f'SWEP.Spread = {self._fmt_num(moa)} * ARC9.MOAToAcc')
        out_lines.append(f'SWEP.SpreadAddHipFire = {self._fmt_num(hip_disp)} * ARC9.MOAToAcc')
        out_lines.append(f'SWEP.SpreadAddMove = {self._fmt_num(move_disp)} * ARC9.MOAToAcc')
        out_lines.append(f'SWEP.SpreadAddSights = {self._fmt_num(sight_disp)} * ARC9.MOAToAcc')
        out_lines.append(f'SWEP.SpreadAddMidAir = {self._fmt_num(jump_disp)} * ARC9.MOAToAcc')

        # 8. Handling
        out_lines.append('\n-------------------------- HANDLING')
        spd = self._get_num("SWEP.SpeedMult", 1)
        spd_sights = self._get_num("SWEP.SightedSpeedMult", 0.8)
        sight_time = self._get_num("SWEP.SightTime", 0.25)
        out_lines.append(f'SWEP.SpeedMult = {self._fmt_num(spd)}')
        out_lines.append(f'SWEP.SpeedMultSights = {self._fmt_num(spd_sights)}')
        out_lines.append(f'SWEP.AimDownSightsTime = {self._fmt_num(sight_time)}')
        out_lines.append(f'SWEP.SprintToFireTime = {self._fmt_num(sight_time * 1.3)}')

        # 9. Positions & Iron Sights
        out_lines.append('\n-------------------------- POSITIONS & SIGHTS')
        ironsights = self.stat_map.get("SWEP.IronSightStruct", self.stat_map.get("SWEP.IronSights"))
        if isinstance(ironsights, LuaTable):
            conv_is = self._convert_ironsights(ironsights)
            out_lines.append(f'SWEP.IronSights = {conv_is.to_lua(0)}')
        else:
            out_lines.append('''SWEP.IronSights = {
    Pos = Vector(0, 0, 0),
    Ang = Angle(0, 0, 0),
    Magnification = 1.15,
}''')

        vm_fov = self._get_num("SWEP.ViewModelFOV", 60)
        out_lines.append(f'SWEP.ViewModelFOVBase = {self._fmt_num(vm_fov)}')

        for pos_name in ["ActivePos", "ActiveAng", "CrouchPos", "CrouchAng", "HolsterPos", "HolsterAng",
                         "SprintPos", "SprintAng"]:
            val = self.stat_map.get(f"SWEP.{pos_name}")
            if val:
                out_lines.append(f'SWEP.{pos_name} = {val.to_lua()}')

        barrel_len = self._get_num("SWEP.BarrelLength")
        if barrel_len:
            out_lines.append(f'SWEP.BarrelLength = {self._fmt_num(barrel_len)}')

        # Heat & Overheat properties
        for heat_stat in ["Jamming", "HeatCapacity", "HeatDissipation", "HeatLockout", "HeatDelayTime", "HeatFix", "HeatOverflow", "HeatPerShot", "HeatGain"]:
            val = self.stat_map.get(f"SWEP.{heat_stat}")
            if val is not None:
                out_lines.append(f'SWEP.{heat_stat} = {val.to_lua()}')

        # 10. Customize / Inspection (Only the gun, properly framed)
        out_lines.append('\n-------------------------- CUSTOMIZE')
        out_lines.append('SWEP.CustomizeAng = Angle(90, 0, 0)')
        out_lines.append('SWEP.CustomizePos = Vector(14, 40, 3)')
        out_lines.append('SWEP.CustomizeRotateAnchor = Vector(14, -3, -4)')
        out_lines.append('SWEP.CustomizeSnapshotFOV = 65')
        out_lines.append('SWEP.CustomizeSnapshotPos = Vector(-1, 30, 0)')
        out_lines.append('SWEP.CustomizeSnapshotAng = Angle(0, 0, 0)')
        out_lines.append('SWEP.CustomizeNoRotate = false')

        # 11. Holdtypes
        out_lines.append('\n-------------------------- HOLDTYPES')
        hold_active = self._get_str("SWEP.HoldtypeActive", self._get_str("SWEP.HoldType", "ar2"))
        hold_holster = self._get_str("SWEP.HoldtypeHolstered", "passive")
        hold_sights = self._get_str("SWEP.HoldtypeSights", hold_active)

        out_lines.append(f'SWEP.HoldType = "{hold_active}"')
        out_lines.append(f'SWEP.HoldTypeNPC = "{hold_active}"')
        out_lines.append(f'SWEP.HoldTypeHolstered = "{hold_holster}"')
        out_lines.append(f'SWEP.HoldTypeSights = "{hold_sights}"')
        out_lines.append('SWEP.HoldTypeCustomize = "slam"')

        anim_shoot = self.stat_map.get("SWEP.AnimShoot")
        if anim_shoot:
            out_lines.append(f'SWEP.AnimShoot = {anim_shoot.to_lua()}')

        # 11. Visual & Audio Effects
        out_lines.append('\n-------------------------- EFFECTS & SOUNDS')
        # Emit any local string helpers (e.g. local path = ..., local tail = ...)
        locals_to_emit = [s for s in self.statements if s.get("is_local")]
        if locals_to_emit:
            for loc in locals_to_emit:
                out_lines.append(f'local {loc["target"]} = {loc["value"].to_lua()}')

        muzzle_fx = self._get_str("SWEP.MuzzleEffect", self._get_str("SWEP.MuzzleParticle"))
        if muzzle_fx:
            out_lines.append(f'SWEP.MuzzleParticle = "{muzzle_fx}"')

        muzzle_qca = self._get_num("SWEP.MuzzleEffectAttachment", self._get_num("SWEP.MuzzleEffectQCA", 1))
        out_lines.append(f'SWEP.MuzzleEffectQCA = {int(muzzle_qca)}')

        case_qca = self._get_num("SWEP.CaseEffectAttachment", self._get_num("SWEP.CaseEffectQCA", 2))
        out_lines.append(f'SWEP.CaseEffectQCA = {int(case_qca)}')

        shell_model = self._get_str("SWEP.ShellModel")
        if shell_model:
            out_lines.append(f'SWEP.ShellModel = "{shell_model}"')
        shell_scale = self._get_num("SWEP.ShellScale")
        if shell_scale is not None:
            out_lines.append(f'SWEP.ShellScale = {self._fmt_num(shell_scale)}')

        tracer_num = self._get_num("SWEP.TracerNum", 1)
        out_lines.append(f'SWEP.TracerNum = {int(tracer_num)}')
        tracer_fx = self._get_str("SWEP.Tracer", self._get_str("SWEP.TracerEffect"))
        if tracer_fx:
            out_lines.append(f'SWEP.TracerEffect = "{tracer_fx}"')

        # Sounds
        shoot_sound = self.stat_map.get("SWEP.ShootSound")
        if shoot_sound:
            out_lines.append(f'SWEP.ShootSound = {shoot_sound.to_lua()}')

        shoot_silenced = self.stat_map.get("SWEP.ShootSoundSilenced")
        if shoot_silenced:
            out_lines.append(f'SWEP.ShootSoundSilenced = {shoot_silenced.to_lua()}')

        dist_outdoors = self.stat_map.get("SWEP.DistantShootSoundOutdoors", self.stat_map.get("SWEP.DistantShootSound"))
        if dist_outdoors:
            out_lines.append(f'SWEP.DistantShootSound = {dist_outdoors.to_lua()}')

        dist_indoors = self.stat_map.get("SWEP.DistantShootSoundIndoors", self.stat_map.get("SWEP.DistantShootSoundIndoor"))
        if dist_indoors:
            out_lines.append(f'SWEP.DistantShootSoundIndoor = {dist_indoors.to_lua()}')

        # Default bodygroups
        bg_str = self._get_str("SWEP.DefaultBodygroups")
        if bg_str:
            out_lines.append(f'\nSWEP.DefaultBodygroups = "{bg_str}"')

        # 12. AttachmentElements
        att_elements = self.stat_map.get("SWEP.AttachmentElements")
        if isinstance(att_elements, LuaTable):
            out_lines.append('\n-------------------------- ATTACHMENT ELEMENTS')
            conv_elements = self._convert_attachment_elements(att_elements)
            out_lines.append(f'SWEP.AttachmentElements = {conv_elements.to_lua(0)}')

        # 13. Attachments Table
        attachments = self.stat_map.get("SWEP.Attachments")
        if isinstance(attachments, LuaTable):
            out_lines.append('\n-------------------------- ATTACHMENTS')
            conv_atts = self._convert_attachments_table(attachments)
            out_lines.append(f'SWEP.Attachments = {conv_atts.to_lua(0)}')

        # 14. Animations Table
        animations = self.stat_map.get("SWEP.Animations")
        if isinstance(animations, LuaTable):
            out_lines.append('\n-------------------------- ANIMATIONS')
            conv_anims = self._convert_animations_table(animations)
            out_lines.append(f'SWEP.Animations = {conv_anims.to_lua(0)}')

        # 15. Other custom functions / hooks / raw statements
        custom_blocks = self._extract_custom_code()
        if custom_blocks:
            out_lines.append('\n-------------------------- CUSTOM FUNCTIONS & HOOKS')
            for blk in custom_blocks:
                out_lines.append(blk)

        return "\n".join(out_lines) + "\n"

    def _convert_firemodes(self, table: LuaTable) -> LuaTable:
        """
        Converts ArcCW firemodes to ARC9 firemodes:
        ArcCW 2 (auto) -> ARC9 -1 (auto)
        ArcCW 1 (semi) -> ARC9 1 (semi)
        ArcCW 0 (safe) -> ARC9 0 (safe)
        ArcCW -N (burst N) -> ARC9 N (burst N)
        """
        new_entries: List[LuaTableEntry] = []
        for e in table.entries:
            if isinstance(e.value, LuaTable):
                mode_val = e.value.get("Mode")
                new_sub_table = LuaTable()
                if isinstance(mode_val, LuaNumber):
                    m = int(mode_val.value)
                    if m == 2:
                        new_mode = -1  # Full auto
                    elif m == 1:
                        new_mode = 1   # Semi
                    elif m == 0:
                        new_mode = 0   # Safe
                    elif m < 0:
                        new_mode = abs(m)  # Burst count
                    else:
                        new_mode = m
                    new_sub_table.set("Mode", LuaNumber(new_mode))
                else:
                    new_sub_table.set("Mode", mode_val if mode_val else LuaNumber(1))

                # Copy any other parameters (e.g. PoseParam, PrintName)
                for sub_e in e.value.entries:
                    if sub_e.key != "Mode" and sub_e.key is not None:
                        new_sub_table.set(str(sub_e.key), sub_e.value)

                new_entries.append(LuaTableEntry(None, new_sub_table))
            else:
                new_entries.append(e)

        return LuaTable(new_entries)

    def _convert_ironsights(self, table: LuaTable) -> LuaTable:
        """Converts ArcCW IronSightStruct to ARC9 IronSights"""
        new_tbl = LuaTable()
        pos = table.get("Pos")
        ang = table.get("Ang")
        mag = table.get("Magnification")
        crosshair = table.get("CrosshairInSights")
        vm_fov = table.get("ViewModelFOV")

        if pos:
            new_tbl.set("Pos", pos)
        if ang:
            new_tbl.set("Ang", ang)
        if mag:
            new_tbl.set("Magnification", mag)
        if vm_fov:
            new_tbl.set("ViewModelFOV", vm_fov)
        if crosshair is not None:
            new_tbl.set("CrosshairInSights", crosshair)
        return new_tbl

    def _convert_attachment_elements(self, table: LuaTable) -> LuaTable:
        """
        Converts ArcCW AttachmentElements:
        - VMBodygroups = {{ind = 1, bg = 2}} -> Bodygroups = {{1, 2}}
        - VMSkin = 1 -> Skin = 1
        """
        new_tbl = LuaTable()
        for e in table.entries:
            ele_key = e.key
            if not isinstance(e.value, LuaTable):
                new_tbl.entries.append(e)
                continue

            sub_tbl = LuaTable()
            # Check VMSkin / Skin
            skin = e.value.get("Skin", e.value.get("VMSkin"))
            if skin:
                sub_tbl.set("Skin", skin)

            # Check VMBodygroups / Bodygroups
            bgs = e.value.get("Bodygroups", e.value.get("VMBodygroups"))
            if isinstance(bgs, LuaTable):
                new_bgs = LuaTable()
                for bg_item in bgs.entries:
                    if isinstance(bg_item.value, LuaTable):
                        # {ind = X, bg = Y} or {X, Y}
                        ind = bg_item.value.get("ind")
                        bg_num = bg_item.value.get("bg")
                        if ind is not None and bg_num is not None:
                            pair = LuaTable([
                                LuaTableEntry(None, ind),
                                LuaTableEntry(None, bg_num)
                            ])
                            new_bgs.entries.append(LuaTableEntry(None, pair))
                        else:
                            new_bgs.entries.append(bg_item)
                    else:
                        new_bgs.entries.append(bg_item)
                sub_tbl.set("Bodygroups", new_bgs)

            # Copy other keys
            for sub_e in e.value.entries:
                if sub_e.key not in ("VMSkin", "Skin", "VMBodygroups", "Bodygroups") and sub_e.key:
                    sub_tbl.set(str(sub_e.key), sub_e.value)

            new_tbl.entries.append(LuaTableEntry(ele_key, sub_tbl))

        return new_tbl

    def _convert_attachments_table(self, table: LuaTable) -> LuaTable:
        """
        Converts ArcCW Attachments array:
        - Slot -> Category (supports table or string)
        - Offset = {vpos = ..., vang = ...} -> Pos = ..., Ang = ...
        - InstalledEles -> InstalledElements
        - DefaultAttName -> DefaultName
        - DefaultAttIcon -> DefaultIcon
        """
        new_tbl = LuaTable()
        for e in table.entries:
            if not isinstance(e.value, LuaTable):
                new_tbl.entries.append(e)
                continue

            att_slot = LuaTable()
            # PrintName
            pname = e.value.get("PrintName")
            if pname:
                att_slot.set("PrintName", pname)

            # DefaultIcon
            icon = e.value.get("DefaultIcon", e.value.get("DefaultAttIcon"))
            if icon:
                att_slot.set("DefaultIcon", icon)

            # DefaultName / DefaultAttName
            dname = e.value.get("DefaultName", e.value.get("DefaultAttName"))
            if dname:
                att_slot.set("DefaultAttName", dname)

            # Bone
            bone = e.value.get("Bone")
            if bone:
                att_slot.set("Bone", bone)

            # Offset: vpos -> Pos, vang -> Ang
            offset = e.value.get("Offset")
            if isinstance(offset, LuaTable):
                vpos = offset.get("vpos", offset.get("Pos"))
                vang = offset.get("vang", offset.get("Ang"))
                if vpos:
                    att_slot.set("Pos", vpos)
                if vang:
                    att_slot.set("Ang", vang)

            # Category from Slot
            slot_cat = e.value.get("Category", e.value.get("Slot"))
            if slot_cat:
                if isinstance(slot_cat, LuaString):
                    # Wrap single category into table: {"cat"}
                    wrapped = LuaTable([LuaTableEntry(None, slot_cat)])
                    att_slot.set("Category", wrapped)
                else:
                    att_slot.set("Category", slot_cat)

            # InstalledElements from InstalledEles
            inst_eles = e.value.get("InstalledElements", e.value.get("InstalledEles"))
            if inst_eles:
                att_slot.set("InstalledElements", inst_eles)

            # CorrectiveAng / CorrectivePos
            c_ang = e.value.get("CorrectiveAng")
            if c_ang:
                att_slot.set("CorrectiveAng", c_ang)
            c_pos = e.value.get("CorrectivePos")
            if c_pos:
                att_slot.set("CorrectivePos", c_pos)

            # FreeSlot
            free_slot = e.value.get("FreeSlot")
            if free_slot is not None:
                att_slot.set("FreeSlot", free_slot)

            # Copy remaining attributes
            for sub_e in e.value.entries:
                k = str(sub_e.key) if sub_e.key else ""
                if k not in ("PrintName", "DefaultIcon", "DefaultAttIcon", "DefaultName", "DefaultAttName",
                             "Bone", "Offset", "Category", "Slot", "InstalledElements", "InstalledEles",
                             "CorrectiveAng", "CorrectivePos", "FreeSlot"):
                    att_slot.set(k, sub_e.value)

            new_tbl.entries.append(LuaTableEntry(None, att_slot))

        return new_tbl

    def _convert_animations_table(self, table: LuaTable) -> LuaTable:
        """
        Converts ArcCW Animations table to ARC9:
        - Keys: enter_inspect/idle_inspect/exit_inspect -> inspect, fire_sights -> fire_iron, etc.
        - Corrects sequence name mismatches (e.g., idle1 -> idle01)
        - SoundTable -> EventTable
        - LHIK -> Normalized IKTimeLine
        - Adds inspect variants (inspect, inspect1, inspect2) only when referenced
        - Generates fallback animations (ready, reload_empty, dryfire, fire_iron)
        """
        new_tbl = LuaTable()

        # Key mappings from ArcCW animation names to ARC9 standard names
        anim_key_map = {
            "idle_sights": "idle_iron",
            "idle_sight": "idle_iron",
            "enter_sight": "enter_sights",
            "exit_sight": "exit_sights",
            "fire_sights": "fire_iron",
            "fire_sight": "fire_iron",
            "sgreload_start": "reload_start",
            "sgreload_start_empty": "reload_start_empty",
            "sgreload_insert": "reload_insert",
            "sgreload_finish": "reload_finish",
            "sgreload_finish_empty": "reload_finish_empty",
        }

        parsed_anims: Dict[str, LuaTable] = {}
        original_order: List[str] = []

        for e in table.entries:
            key_name = ""
            if isinstance(e.key, LuaString):
                key_name = e.key.value
            elif isinstance(e.key, str):
                key_name = e.key
            else:
                key_name = str(e.key)

            target_key = anim_key_map.get(key_name, key_name)
            if target_key not in original_order:
                original_order.append(target_key)

            if not isinstance(e.value, LuaTable):
                sub_anim = LuaTable([LuaTableEntry(None, e.value)])
                parsed_anims[target_key] = sub_anim
                continue

            sub_anim = LuaTable()

            # Source with sequence correction (e.g. idle1 -> idle01)
            src = e.value.get("Source")
            if src:
                sub_anim.set("Source", self._fix_source_sequence(src))

            # Time / Mult / MinProgress / FireASAP
            time_val = e.value.get("Time")
            if time_val:
                sub_anim.set("Time", time_val)

            mult = e.value.get("Mult")
            if mult:
                sub_anim.set("Mult", mult)

            # Set reasonable reload & draw flags for ARC9
            if "reload" in target_key:
                if target_key in ("reload_insert", "sgreload_insert"):
                    sub_anim.set("MinProgress", LuaNumber(0.5))
                else:
                    sub_anim.set("MinProgress", LuaNumber(0.65))
                sub_anim.set("FireASAP", LuaBool(True))
            elif target_key in ("draw", "ready"):
                sub_anim.set("MinProgress", LuaNumber(0.5))
                sub_anim.set("FireASAP", LuaBool(True))
            elif "inspect" in target_key:
                sub_anim.set("MinProgress", LuaNumber(0.85))
                sub_anim.set("FireASAP", LuaBool(True))

            # LHIK -> IKTimeLine
            lhik = e.value.get("LHIK")
            if lhik and isinstance(lhik, LuaBool) and lhik.value:
                timeline = self._make_ik_timeline(target_key, e.value)
                sub_anim.set("IKTimeLine", timeline)

            # SoundTable -> EventTable
            sound_tbl = e.value.get("EventTable", e.value.get("SoundTable"))
            if isinstance(sound_tbl, LuaTable):
                sub_anim.set("EventTable", sound_tbl)

            # Copy remaining fields
            for sub_e in e.value.entries:
                sk = str(sub_e.key) if sub_e.key else ""
                if sk not in ("Source", "Time", "Mult", "LHIK", "LHIKIn", "LHIKOut", "SoundTable", "EventTable",
                             "MinProgress", "FireASAP", "IKTimeLine"):
                    sub_anim.set(sk, sub_e.value)

            parsed_anims[target_key] = sub_anim

        # Post-processing: Ensure inspect animation exists for single-key inspection (+inspect / E+R)
        if "inspect" not in parsed_anims:
            chosen_inspect = None
            for candidate in ("idle_inspect", "exit_inspect", "enter_inspect"):
                if candidate in parsed_anims:
                    chosen_inspect = candidate
                    break
            if chosen_inspect:
                parsed_anims["inspect"] = self._clone_table(parsed_anims[chosen_inspect])
                original_order.append("inspect")

        # Post-processing: Ensure inspect_empty exists if empty inspect variants exist
        if "inspect_empty" not in parsed_anims:
            chosen_inspect_empty = None
            for candidate in ("idle_inspect_empty", "exit_inspect_empty", "enter_inspect_empty"):
                if candidate in parsed_anims:
                    chosen_inspect_empty = candidate
                    break
            if chosen_inspect_empty:
                parsed_anims["inspect_empty"] = self._clone_table(parsed_anims[chosen_inspect_empty])
                original_order.append("inspect_empty")

        # Post-processing: Ensure unjam exists if fix exists
        if "fix" in parsed_anims and "unjam" not in parsed_anims:
            parsed_anims["unjam"] = self._clone_table(parsed_anims["fix"])
            original_order.append("unjam")

        # Post-processing: Add inspect variants (inspect1, inspect2) only if referenced
        has_inspect_vars = any("inspect1" in stmt.get("code", "") for stmt in self.statements) or \
                           any("inspect1" in str(s.to_lua()) for s in self.stat_map.values())
        if has_inspect_vars and "inspect" in parsed_anims:
            base_inspect = parsed_anims["inspect"]
            base_inspect.set("Source", LuaTable([
                LuaTableEntry(None, LuaString("inspect1")),
                LuaTableEntry(None, LuaString("inspect2")),
            ]))
            if "inspect1" not in parsed_anims:
                ins1 = self._clone_table(base_inspect)
                ins1.set("Source", LuaString("inspect1"))
                parsed_anims["inspect1"] = ins1
                original_order.append("inspect1")
            if "inspect2" not in parsed_anims:
                ins2 = self._clone_table(base_inspect)
                ins2.set("Source", LuaString("inspect2"))
                parsed_anims["inspect2"] = ins2
                original_order.append("inspect2")

        # Post-processing: Add ready if draw exists
        if "draw" in parsed_anims and "ready" not in parsed_anims:
            ready_anim = self._clone_table(parsed_anims["draw"])
            ready_anim.set("MinProgress", LuaNumber(0.5))
            ready_anim.set("FireASAP", LuaBool(True))
            parsed_anims["ready"] = ready_anim
            draw_idx = original_order.index("draw")
            original_order.insert(draw_idx + 1, "ready")

        # Post-processing: Add fallback reload if shotgun reload is present but standard reload is not
        if "reload" not in parsed_anims:
            if "reload_insert" in parsed_anims:
                parsed_anims["reload"] = self._clone_table(parsed_anims["reload_insert"])
                original_order.append("reload")
            elif "reload_start" in parsed_anims:
                parsed_anims["reload"] = self._clone_table(parsed_anims["reload_start"])
                original_order.append("reload")

        # Post-processing: Add reload_empty if reload exists
        if "reload" in parsed_anims and "reload_empty" not in parsed_anims:
            r_empty = self._clone_table(parsed_anims["reload"])
            parsed_anims["reload_empty"] = r_empty
            reload_idx = original_order.index("reload")
            original_order.insert(reload_idx + 1, "reload_empty")

        # Post-processing: Add dryfire if fire exists
        if "dryfire" not in parsed_anims:
            dry_src = None
            if "fire_empty" in parsed_anims:
                dry_src = parsed_anims["fire_empty"].get("Source")
            elif "fire" in parsed_anims:
                dry_src = parsed_anims["fire"].get("Source")
            if dry_src:
                dry_anim = LuaTable([
                    LuaTableEntry("Source", dry_src),
                    LuaTableEntry("MinProgress", LuaNumber(0.01)),
                    LuaTableEntry("FireASAP", LuaBool(True)),
                    LuaTableEntry("Mult", LuaNumber(0.3)),
                ])
                parsed_anims["dryfire"] = dry_anim
                ref_key = "fire_empty" if "fire_empty" in parsed_anims else "fire"
                ref_idx = original_order.index(ref_key)
                original_order.insert(ref_idx + 1, "dryfire")

        # Build final table in ordered sequence
        for k in original_order:
            if k in parsed_anims:
                new_tbl.entries.append(LuaTableEntry(LuaString(k), parsed_anims[k]))

        return new_tbl

    def _fix_source_sequence(self, val: Any) -> Any:
        seq_map = {
            "idle1": "idle01",
        }
        if isinstance(val, LuaString):
            return LuaString(seq_map.get(val.value, val.value))
        elif isinstance(val, LuaTable):
            new_entries = []
            for ent in val.entries:
                if isinstance(ent.value, LuaString):
                    new_entries.append(LuaTableEntry(ent.key, LuaString(seq_map.get(ent.value.value, ent.value.value))))
                else:
                    new_entries.append(ent)
            return LuaTable(new_entries)
        return val

    def _clone_table(self, table: LuaTable) -> LuaTable:
        new_entries = []
        for e in table.entries:
            val = e.value
            if isinstance(val, LuaTable):
                val = self._clone_table(val)
            new_entries.append(LuaTableEntry(e.key, val))
        return LuaTable(new_entries)

    def _make_ik_timeline(self, anim_key: str, tbl: LuaTable) -> LuaTable:
        lhik_in = self._get_table_num(tbl, "LHIKIn", 0.2)
        lhik_out = self._get_table_num(tbl, "LHIKOut", 0.2)
        time_val = self._get_table_num(tbl, "Time", 0.0)

        if time_val <= 0:
            if "reload" in anim_key:
                anim_time = 2.5
            elif "draw" in anim_key or "ready" in anim_key:
                anim_time = 0.8
            elif "inspect" in anim_key:
                anim_time = 3.0
            else:
                anim_time = 1.0
        else:
            anim_time = time_val

        t_in = 0.0 if lhik_in == 0 else min(0.35, round(lhik_in / anim_time, 2))
        t_out = max(t_in + 0.1, min(0.9, round(1.0 - (lhik_out / anim_time), 2)))
        t_end = min(1.0, round(t_out + 0.1, 2))

        entries = [
            LuaTableEntry(None, LuaTable([
                LuaTableEntry("t", LuaNumber(0)),
                LuaTableEntry("lhik", LuaNumber(0 if lhik_in == 0 else 1)),
                LuaTableEntry("rhik", LuaNumber(1))
            ]))
        ]
        if t_in > 0:
            entries.append(LuaTableEntry(None, LuaTable([
                LuaTableEntry("t", LuaNumber(t_in)),
                LuaTableEntry("lhik", LuaNumber(0)),
                LuaTableEntry("rhik", LuaNumber(1))
            ])))
        entries.append(LuaTableEntry(None, LuaTable([
            LuaTableEntry("t", LuaNumber(t_out)),
            LuaTableEntry("lhik", LuaNumber(0)),
            LuaTableEntry("rhik", LuaNumber(1))
        ])))
        entries.append(LuaTableEntry(None, LuaTable([
            LuaTableEntry("t", LuaNumber(t_end)),
            LuaTableEntry("lhik", LuaNumber(1)),
            LuaTableEntry("rhik", LuaNumber(1))
        ])))

        return LuaTable(entries)

    def _extract_custom_code(self) -> List[str]:
        """Extracts and adapts custom statements, hooks, and injects the customize handler."""
        blocks = []
        has_hook_think = False

        # Check if weapon uses Heat / Overheat mechanics
        has_heat = any(self.stat_map.get(f"SWEP.{s}") is not None for s in [
            "Jamming", "HeatCapacity", "HeatDissipation", "HeatLockout", "HeatDelayTime", "HeatFix", "HeatOverflow"
        ])

        if has_heat:
            heat_methods = '''-------------------------- HEAT & OVERHEAT (ArcCW Compatibility)
function SWEP:GetHeat()
    return self:GetNWFloat("arc9_heat", 0)
end

function SWEP:SetHeat(val)
    self:SetNWFloat("arc9_heat", math.Clamp(val, 0, self:GetMaxHeat()))
end

function SWEP:GetMaxHeat()
    return self.HeatCapacity or 100
end'''
            blocks.append(heat_methods)

        for stmt in self.statements:
            if stmt["type"] == "function":
                code = stmt["code"]
                code = self._adapt_function_code(code)
                blocks.append(code)
            elif stmt["type"] == "assignment":
                target = stmt["target"]
                if target == "SWEP.Hook_Think":
                    has_hook_think = True
                if target.startswith("SWEP.Hook_"):
                    code = stmt["value"].to_lua()
                    code = self._adapt_function_code(code)
                    blocks.append(f"{target} = {code}")

        # Inject customization menu handler: only the gun, no animations
        cust_body = '''    if CLIENT then
        local cust = (wep.GetCustomize and wep:GetCustomize()) or ((wep.CustomizeDelta or 0) > 0)
        local vm = IsValid(wep:GetVM()) and wep:GetVM()
        local owner = wep:GetOwner()
        local hands = IsValid(owner) and owner:GetHands()

        if cust then
            -- Hide player hands during customization (only the gun)
            if IsValid(hands) then
                hands:SetRenderMode(RENDERMODE_NONE)
            end

            if vm then
                -- Freeze viewmodel animation during customization (no animations)
                vm:SetPlaybackRate(0)
                if not wep._arc9_cust_frozen then
                    vm:SetCycle(0)
                    wep._arc9_cust_frozen = true
                end

                -- Hide arm and hand bones on the viewmodel model
                for i = 0, (vm:GetBoneCount() - 1) do
                    local bname = vm:GetBoneName(i)
                    if bname then
                        local lower = string.lower(bname)
                        if string.find(lower, "bip01_l_") or string.find(lower, "bip01_r_")
                            or string.find(lower, "valvebiped") or string.find(lower, "arm")
                            or string.find(lower, "hand") or string.find(lower, "finger")
                            or string.find(lower, "wrist") or string.find(lower, "forearm") then
                            vm:ManipulateBoneScale(i, Vector(0, 0, 0))
                        end
                    end
                end
            end
        else
            -- Restore hands and animation playback when leaving customize menu
            if wep._arc9_cust_frozen then
                wep._arc9_cust_frozen = false
                if IsValid(hands) and hands:GetRenderMode() == RENDERMODE_NONE then
                    hands:SetRenderMode(RENDERMODE_NORMAL)
                end
                if vm then
                    vm:SetPlaybackRate(1)
                    for i = 0, (vm:GetBoneCount() - 1) do
                        vm:ManipulateBoneScale(i, Vector(1, 1, 1))
                    end
                end
            end
        end
    end

    -- Heat decay simulation
    if wep.HeatCapacity then
        local heat = (wep.GetHeat and wep:GetHeat()) or wep:GetNWFloat("arc9_heat", 0)
        if heat > 0 and CurTime() > (wep._last_shot_time or 0) + (wep.HeatDelayTime or 0.1) then
            local decay = (wep.HeatDissipation or 10) * FrameTime()
            local new_heat = math.max(0, heat - decay)
            if wep.SetHeat then
                wep:SetHeat(new_heat)
            else
                wep:SetNWFloat("arc9_heat", new_heat)
            end
            if new_heat <= 0 then
                wep._heat_locked = false
            end
        end
    end'''

        if has_hook_think:
            cust_handler = f'''local _old_Hook_Think = SWEP.Hook_Think
SWEP.Hook_Think = function(wep)
    if _old_Hook_Think then _old_Hook_Think(wep) end
{cust_body}
end'''
        else:
            cust_handler = f'''SWEP.Hook_Think = function(wep)
{cust_body}
end'''

        blocks.append(cust_handler)

        if has_heat:
            primary_attack_hook = '''local _old_Hook_PrimaryAttack = SWEP.Hook_PrimaryAttack
SWEP.Hook_PrimaryAttack = function(wep)
    if _old_Hook_PrimaryAttack then _old_Hook_PrimaryAttack(wep) end
    if wep.HeatCapacity then
        wep._last_shot_time = CurTime()
        local cur = (wep.GetHeat and wep:GetHeat()) or wep:GetNWFloat("arc9_heat", 0)
        local nxt = cur + (wep.HeatPerShot or wep.HeatGain or 1)
        if wep.SetHeat then
            wep:SetHeat(nxt)
        else
            wep:SetNWFloat("arc9_heat", nxt)
        end
        if nxt >= (wep.GetMaxHeat and wep:GetMaxHeat() or wep.HeatCapacity or 100) and wep.HeatLockout then
            wep._heat_locked = true
        end
    end
end'''
            blocks.append(primary_attack_hook)

        return blocks

    def _adapt_function_code(self, code: str) -> str:
        code = re.sub(r'\bArcCW\b', 'ARC9', code)
        code = re.sub(r'anim\s*==\s*["\']enter_inspect["\']', 'anim == "inspect" or anim == "enter_inspect"', code)
        code = re.sub(r'anim\s*==\s*["\']sgreload_start["\']', 'anim == "reload_start" or anim == "sgreload_start"', code)
        code = re.sub(r'anim\s*==\s*["\']sgreload_insert["\']', 'anim == "reload_insert" or anim == "sgreload_insert"', code)
        code = re.sub(r'anim\s*==\s*["\']sgreload_finish["\']', 'anim == "reload_finish" or anim == "sgreload_finish"', code)
        code = re.sub(r'\bMyEmitSound\b', 'EmitSound', code)
        code = re.sub(r'wep:GetSightDelta\(\)', '(wep.GetSightDelta and wep:GetSightDelta() or wep:GetSightAmount())', code)
        code = re.sub(r'(?:wep|self):GetHeat\(\)', '((wep or self).GetHeat and (wep or self):GetHeat() or (wep or self):GetNWFloat("arc9_heat", 0))', code)
        code = re.sub(r'(?:wep|self):GetMaxHeat\(\)', '((wep or self).GetMaxHeat and (wep or self):GetMaxHeat() or (wep or self).HeatCapacity or 100)', code)
        return code

    def _get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        v = self.stat_map.get(key)
        if isinstance(v, LuaString):
            return v.value
        return default

    def _get_num(self, key: str, default: Optional[Union[int, float]] = None) -> Optional[Union[int, float]]:
        v = self.stat_map.get(key)
        if isinstance(v, LuaNumber):
            return v.value
        return default

    def _get_bool(self, key: str, default: bool = False) -> bool:
        v = self.stat_map.get(key)
        if isinstance(v, LuaBool):
            return v.value
        return default

    def _get_table_num(self, table: LuaTable, key: str, default: float) -> float:
        v = table.get(key)
        if isinstance(v, LuaNumber):
            return float(v.value)
        return default

    def _fmt_num(self, num: Union[int, float]) -> str:
        if isinstance(num, int):
            return str(num)
        # Check if integer float
        if num == int(num):
            return str(int(num))
        return f"{num:g}"
