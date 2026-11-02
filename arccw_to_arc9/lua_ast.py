"""
Lua Value and AST Representation for GMod Lua
"""
from typing import Any, List, Optional, Tuple, Union

class LuaValue:
    """Base class for parsed Lua values"""
    def to_lua(self, indent: int = 0) -> str:
        raise NotImplementedError

class LuaNil(LuaValue):
    def to_lua(self, indent: int = 0) -> str:
        return "nil"

    def __repr__(self):
        return "LuaNil()"

class LuaBool(LuaValue):
    def __init__(self, value: bool):
        self.value = value

    def to_lua(self, indent: int = 0) -> str:
        return "true" if self.value else "false"

    def __repr__(self):
        return f"LuaBool({self.value})"

class LuaNumber(LuaValue):
    def __init__(self, value: Union[int, float], raw: Optional[str] = None):
        self.value = value
        self.raw = raw if raw is not None else str(value)

    def to_lua(self, indent: int = 0) -> str:
        return self.raw

    def __repr__(self):
        return f"LuaNumber({self.value})"

class LuaString(LuaValue):
    def __init__(self, value: str, quote: str = '"'):
        self.value = value
        self.quote = quote

    def to_lua(self, indent: int = 0) -> str:
        if self.quote in ('[[', '[=[', '[==['):
            return f"[[{self.value}]]"
        # Escaped string
        escaped = self.value.replace('\\', '\\\\')
        if self.quote == '"':
            escaped = escaped.replace('"', '\\"').replace('\n', '\\n')
            return f'"{escaped}"'
        else:
            escaped = escaped.replace("'", "\\'").replace('\n', '\\n')
            return f"'{escaped}'"

    def __repr__(self):
        return f"LuaString({repr(self.value)})"

class LuaVector(LuaValue):
    def __init__(self, x: float, y: float, z: float, raw: Optional[str] = None):
        self.x = x
        self.y = y
        self.z = z
        self.raw = raw

    def to_lua(self, indent: int = 0) -> str:
        if self.raw:
            return self.raw
        # Format cleanly
        fx = f"{self.x:g}"
        fy = f"{self.y:g}"
        fz = f"{self.z:g}"
        return f"Vector({fx}, {fy}, {fz})"

    def __repr__(self):
        return f"LuaVector({self.x}, {self.y}, {self.z})"

class LuaAngle(LuaValue):
    def __init__(self, p: float, y: float, r: float, raw: Optional[str] = None):
        self.p = p
        self.y = y
        self.r = r
        self.raw = raw

    def to_lua(self, indent: int = 0) -> str:
        if self.raw:
            return self.raw
        fp = f"{self.p:g}"
        fy = f"{self.y:g}"
        fr = f"{self.r:g}"
        return f"Angle({fp}, {fy}, {fr})"

    def __repr__(self):
        return f"LuaAngle({self.p}, {self.y}, {self.r})"

class LuaColor(LuaValue):
    def __init__(self, r: int, g: int, b: int, a: int = 255, raw: Optional[str] = None):
        self.r = r
        self.g = g
        self.b = b
        self.a = a
        self.raw = raw

    def to_lua(self, indent: int = 0) -> str:
        if self.raw:
            return self.raw
        if self.a == 255:
            return f"Color({self.r}, {self.g}, {self.b})"
        return f"Color({self.r}, {self.g}, {self.b}, {self.a})"

    def __repr__(self):
        return f"LuaColor({self.r}, {self.g}, {self.b}, {self.a})"

class LuaMaterial(LuaValue):
    def __init__(self, path: str, params: Optional[str] = None, raw: Optional[str] = None):
        self.path = path
        self.params = params
        self.raw = raw

    def to_lua(self, indent: int = 0) -> str:
        if self.raw:
            return self.raw
        if self.params:
            return f'Material("{self.path}", "{self.params}")'
        return f'Material("{self.path}")'

    def __repr__(self):
        return f"LuaMaterial({repr(self.path)}, {repr(self.params)})"

class LuaRaw(LuaValue):
    """Raw verbatim Lua expression or code snippet"""
    def __init__(self, code: str):
        self.code = code.strip()

    def to_lua(self, indent: int = 0) -> str:
        return self.code

    def __repr__(self):
        return f"LuaRaw({repr(self.code)})"

class LuaTableEntry:
    def __init__(self, key: Optional[Union[str, LuaValue]], value: LuaValue, comment: Optional[str] = None):
        self.key = key  # None means sequential array element
        self.value = value
        self.comment = comment

    def __repr__(self):
        return f"LuaTableEntry(key={repr(self.key)}, value={repr(self.value)})"

class LuaTable(LuaValue):
    def __init__(self, entries: Optional[List[LuaTableEntry]] = None):
        self.entries: List[LuaTableEntry] = entries if entries is not None else []

    def is_array(self) -> bool:
        return all(e.key is None for e in self.entries)

    def is_simple(self) -> bool:
        """Check if all values are primitives and short enough for a single line"""
        if len(self.entries) > 6:
            return False
        for e in self.entries:
            if isinstance(e.value, LuaTable):
                return False
            if isinstance(e.value, LuaRaw) and ('\n' in e.value.code or len(e.value.code) > 30):
                return False
        return True

    def get(self, key: str, default: Any = None) -> Any:
        for e in self.entries:
            if isinstance(e.key, str) and e.key == key:
                return e.value
            if isinstance(e.key, LuaString) and e.key.value == key:
                return e.value
        return default

    def set(self, key: str, value: LuaValue):
        for e in self.entries:
            if (isinstance(e.key, str) and e.key == key) or (isinstance(e.key, LuaString) and e.key.value == key):
                e.value = value
                return
        self.entries.append(LuaTableEntry(key, value))

    def remove(self, key: str) -> bool:
        for i, e in enumerate(self.entries):
            if (isinstance(e.key, str) and e.key == key) or (isinstance(e.key, LuaString) and e.key.value == key):
                del self.entries[i]
                return True
        return False

    def to_lua(self, indent: int = 0) -> str:
        if not self.entries:
            return "{}"

        # If simple and short, format inline
        if self.is_simple():
            parts = []
            for e in self.entries:
                val_str = e.value.to_lua(indent)
                if e.key is None:
                    parts.append(val_str)
                elif isinstance(e.key, str) and e.key.isidentifier():
                    parts.append(f"{e.key} = {val_str}")
                elif isinstance(e.key, LuaString):
                    parts.append(f'["{e.key.value}"] = {val_str}')
                elif isinstance(e.key, LuaValue):
                    parts.append(f'[{e.key.to_lua()}] = {val_str}')
                else:
                    parts.append(f'["{e.key}"] = {val_str}')
            line = "{ " + ", ".join(parts) + " }"
            if len(line) < 80:
                return line

        # Multiline indented format
        pad = "    " * indent
        subpad = "    " * (indent + 1)
        lines = ["{"]
        for e in self.entries:
            val_str = e.value.to_lua(indent + 1)
            comment_str = f" -- {e.comment}" if e.comment else ""
            if e.key is None:
                lines.append(f"{subpad}{val_str},{comment_str}")
            elif isinstance(e.key, str) and e.key.isidentifier():
                lines.append(f"{subpad}{e.key} = {val_str},{comment_str}")
            elif isinstance(e.key, LuaString):
                lines.append(f'{subpad}["{e.key.value}"] = {val_str},{comment_str}')
            elif isinstance(e.key, LuaValue):
                lines.append(f'{subpad}[{e.key.to_lua()}] = {val_str},{comment_str}')
            else:
                lines.append(f'{subpad}["{e.key}"] = {val_str},{comment_str}')
        lines.append(f"{pad}}}")
        return "\n".join(lines)

    def __repr__(self):
        return f"LuaTable({self.entries})"
