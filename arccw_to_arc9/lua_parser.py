"""
Lua Parser for SWEP and Attachment Files
"""
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from .lua_tokenizer import LuaTokenizer, Token
from .lua_ast import (
    LuaValue, LuaNil, LuaBool, LuaNumber, LuaString,
    LuaVector, LuaAngle, LuaColor, LuaMaterial, LuaRaw,
    LuaTable, LuaTableEntry
)

class LuaParser:
    def __init__(self, text: str):
        self.text = text
        self.tokens: List[Token] = []
        self.pos = 0

    def parse(self) -> Tuple[List[Dict[str, Any]], Dict[str, LuaValue]]:
        """
        Parses Lua code into a list of top-level statements/elements:
        - {"type": "assignment", "target": "SWEP.Damage", "value": LuaValue, "raw": "..."}
        - {"type": "function", "name": "SWEP:Hook_Think", "code": "..."}
        - {"type": "raw", "code": "..."}
        - {"type": "comment", "comment": "..."}
        Also returns a dict of target -> LuaValue for easy stat lookup.
        """
        # Tokenize preserving comments
        tokenizer = LuaTokenizer(self.text)
        all_tokens = tokenizer.tokenize(include_comments=True)
        self.tokens = [t for t in all_tokens if t.type != "WHITESPACE"]
        self.pos = 0

        statements: List[Dict[str, Any]] = []
        stat_map: Dict[str, LuaValue] = {}

        while self.pos < len(self.tokens):
            tok = self.tokens[self.pos]

            if tok.type == "COMMENT":
                statements.append({"type": "comment", "comment": tok.value})
                self.pos += 1
                continue

            # Check for function definition: function SWEP:Name(...) ... end or local function Name(...) ... end
            if (tok.type == "IDENT" and tok.value == "function") or \
               (tok.type == "IDENT" and tok.value == "local" and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].value == "function"):
                func_code, next_pos = self._extract_function_block(self.pos)
                if func_code:
                    statements.append({"type": "function", "code": func_code})
                    self.pos = next_pos
                    continue

            # Check for SWEP.xxx = ... or att.xxx = ... or target = ...
            if tok.type == "IDENT":
                # Lookahead for assignment: [local] IDENT ( ('.' or ':') IDENT )* '='
                assign_target, eq_pos, is_local = self._check_assignment_target(self.pos)
                if assign_target and eq_pos is not None:
                    self.pos = eq_pos + 1  # Move past '='
                    val, next_pos = self._parse_expression(self.pos)
                    # Optional trailing semicolon or comma
                    if next_pos < len(self.tokens) and self.tokens[next_pos].value in (';', ','):
                        next_pos += 1
                    statements.append({
                        "type": "assignment",
                        "target": assign_target,
                        "value": val,
                        "is_local": is_local
                    })
                    stat_map[assign_target] = val
                    self.pos = next_pos
                    continue

            # Otherwise, collect raw line / statement until newline or statement end
            raw_statement, next_pos = self._extract_raw_statement(self.pos)
            if raw_statement:
                statements.append({"type": "raw", "code": raw_statement})
            self.pos = next_pos

        return statements, stat_map

    def _check_assignment_target(self, start: int) -> Tuple[Optional[str], Optional[int], bool]:
        """Checks if tokens starting at start form an assignment `Target = ...`
        Returns (target_name, eq_pos, is_local)
        """
        i = start
        is_local = False
        if i < len(self.tokens) and self.tokens[i].type == "IDENT" and self.tokens[i].value == "local":
            is_local = True
            i += 1

        parts = []
        while i < len(self.tokens):
            t = self.tokens[i]
            if t.type == "IDENT":
                parts.append(t.value)
                i += 1
            elif t.type == "SYMBOL" and t.value in ('.', ':'):
                parts.append(t.value)
                i += 1
            elif t.type == "SYMBOL" and t.value == '[':
                # e.g. BodyDamageMults[HITGROUP_HEAD]
                bracket_expr = []
                i += 1
                bracket_depth = 1
                while i < len(self.tokens) and bracket_depth > 0:
                    if self.tokens[i].value == '[':
                        bracket_depth += 1
                    elif self.tokens[i].value == ']':
                        bracket_depth -= 1
                    if bracket_depth > 0:
                        bracket_expr.append(self.tokens[i].value)
                    i += 1
                parts.append(f"[{''.join(bracket_expr)}]")
            else:
                break

        if parts and i < len(self.tokens) and self.tokens[i].type == "SYMBOL" and self.tokens[i].value == '=':
            target_str = "".join(parts)
            return target_str, i, is_local
        return None, None, False

    def _parse_expression(self, start: int) -> Tuple[LuaValue, int]:
        """Parses an expression starting at token index start"""
        if start >= len(self.tokens):
            return LuaNil(), start

        tok = self.tokens[start]

        # Table: { ... }
        if tok.type == "SYMBOL" and tok.value == '{':
            return self._parse_table(start)

        # Function literal: function(...) ... end
        if tok.type == "IDENT" and tok.value == "function":
            code, next_pos = self._extract_function_block(start)
            return LuaRaw(code), next_pos

        # Vector(x, y, z)
        if tok.type == "IDENT" and tok.value == "Vector" and self._peek_sym(start + 1, '('):
            vec, next_pos = self._parse_call_args(start + 2)
            if len(vec) == 3:
                try:
                    vx = float(re.sub(r'\s+', '', vec[0]))
                    vy = float(re.sub(r'\s+', '', vec[1]))
                    vz = float(re.sub(r'\s+', '', vec[2]))
                    return LuaVector(vx, vy, vz), next_pos
                except ValueError:
                    pass
            # Fallback to LuaRaw
            code = self._slice_tokens(start, next_pos)
            return LuaRaw(code), next_pos

        # Angle(p, y, r)
        if tok.type == "IDENT" and tok.value == "Angle" and self._peek_sym(start + 1, '('):
            ang, next_pos = self._parse_call_args(start + 2)
            if len(ang) == 3:
                try:
                    ap = float(re.sub(r'\s+', '', ang[0]))
                    ay = float(re.sub(r'\s+', '', ang[1]))
                    ar = float(re.sub(r'\s+', '', ang[2]))
                    return LuaAngle(ap, ay, ar), next_pos
                except ValueError:
                    pass
            code = self._slice_tokens(start, next_pos)
            return LuaRaw(code), next_pos

        # Color(r, g, b, [a])
        if tok.type == "IDENT" and tok.value == "Color" and self._peek_sym(start + 1, '('):
            col, next_pos = self._parse_call_args(start + 2)
            if len(col) in (3, 4):
                try:
                    r = int(float(re.sub(r'\s+', '', col[0])))
                    g = int(float(re.sub(r'\s+', '', col[1])))
                    b = int(float(re.sub(r'\s+', '', col[2])))
                    a = int(float(re.sub(r'\s+', '', col[3]))) if len(col) == 4 else 255
                    return LuaColor(r, g, b, a), next_pos
                except ValueError:
                    pass
            code = self._slice_tokens(start, next_pos)
            return LuaRaw(code), next_pos

        # Material("path", ["params"])
        if tok.type == "IDENT" and tok.value == "Material" and self._peek_sym(start + 1, '('):
            args, next_pos = self._parse_call_args(start + 2)
            if len(args) >= 1:
                p = args[0].strip('"\'')
                m = args[1].strip('"\'') if len(args) > 1 else None
                return LuaMaterial(p, m), next_pos
            code = self._slice_tokens(start, next_pos)
            return LuaRaw(code), next_pos

        # Simple literals
        if tok.type == "IDENT":
            if tok.value == "nil":
                return LuaNil(), start + 1
            if tok.value == "true":
                return LuaBool(True), start + 1
            if tok.value == "false":
                return LuaBool(False), start + 1

        if tok.type == "STRING":
            content, quote = self._extract_string_content(tok.value)
            # Check if there is concatenation: str .. expr
            if self._peek_sym(start + 1, '..'):
                raw_expr, next_pos = self._extract_expression_chain(start)
                return LuaRaw(raw_expr), next_pos
            return LuaString(content, quote), start + 1

        # Negative numbers: -NUMBER
        if tok.type == "SYMBOL" and tok.value == '-' and start + 1 < len(self.tokens) and self.tokens[start+1].type == "NUMBER":
            num_tok = self.tokens[start+1]
            raw_val = f"-{num_tok.value}"
            try:
                if '.' in num_tok.value or 'e' in num_tok.value.lower():
                    return LuaNumber(-float(num_tok.value), raw=raw_val), start + 2
                return LuaNumber(-int(num_tok.value, 0 if num_tok.value.startswith('0x') else 10), raw=raw_val), start + 2
            except ValueError:
                pass

        if tok.type == "NUMBER":
            val_str = tok.value
            # Check if part of arithmetic: e.g. 60 / 100 or 14/40
            if start + 1 < len(self.tokens) and self.tokens[start+1].value in ('+', '-', '*', '/', '^', '%'):
                raw_expr, next_pos = self._extract_expression_chain(start)
                # Try evaluating simple arithmetic
                try:
                    eval_val = eval(raw_expr, {"__builtins__": None}, {})
                    if isinstance(eval_val, (int, float)):
                        return LuaNumber(eval_val, raw=raw_expr), next_pos
                except Exception:
                    pass
                return LuaRaw(raw_expr), next_pos
            try:
                if '.' in val_str or 'e' in val_str or 'E' in val_str:
                    return LuaNumber(float(val_str), raw=val_str), start + 1
                return LuaNumber(int(val_str, 0 if val_str.startswith('0x') else 10), raw=val_str), start + 1
            except ValueError:
                return LuaNumber(0, raw=val_str), start + 1

        # Function expression: function(...) ... end
        if tok.type == "IDENT" and tok.value == "function":
            func_code, next_pos = self._extract_function_block(start)
            return LuaRaw(func_code), next_pos

        # Fallback: extract expression chain until delimiter
        raw_expr, next_pos = self._extract_expression_chain(start)
        return LuaRaw(raw_expr), next_pos

    def _parse_table(self, start: int) -> Tuple[LuaTable, int]:
        """Parses `{ ... }`"""
        i = start + 1  # past '{'
        entries: List[LuaTableEntry] = []

        while i < len(self.tokens):
            t = self.tokens[i]

            if t.type == "COMMENT":
                i += 1
                continue

            if t.type == "SYMBOL" and t.value == '}':
                return LuaTable(entries), i + 1

            # Check if key = value or [expr] = value
            # Case 1: [expr] = value
            if t.type == "SYMBOL" and t.value == '[':
                key_expr, next_i = self._extract_bracket_key(i)
                if next_i < len(self.tokens) and self.tokens[next_i].value == '=':
                    val, val_end = self._parse_expression(next_i + 1)
                    entries.append(LuaTableEntry(key_expr, val))
                    i = val_end
                    if i < len(self.tokens) and self.tokens[i].value in (',', ';'):
                        i += 1
                    continue

            # Case 2: IDENT = value
            if t.type == "IDENT" and i + 1 < len(self.tokens) and self.tokens[i+1].value == '=':
                key_name = t.value
                val, val_end = self._parse_expression(i + 2)
                entries.append(LuaTableEntry(key_name, val))
                i = val_end
                if i < len(self.tokens) and self.tokens[i].value in (',', ';'):
                    i += 1
                continue

            # Case 3: STRING = value (GMod Lua allows ["foo"] = val or 'foo' = val in some contexts)
            # Or Sequential value: expr
            val, val_end = self._parse_expression(i)
            entries.append(LuaTableEntry(None, val))
            i = val_end
            if i < len(self.tokens) and self.tokens[i].value in (',', ';'):
                i += 1

        return LuaTable(entries), i

    def _extract_bracket_key(self, start: int) -> Tuple[Union[str, LuaValue], int]:
        """Extracts key inside `[ ... ]`"""
        i = start + 1
        depth = 1
        bracket_tokens = []
        while i < len(self.tokens) and depth > 0:
            t = self.tokens[i]
            if t.value == '[':
                depth += 1
            elif t.value == ']':
                depth -= 1
                if depth == 0:
                    break
            bracket_tokens.append(t)
            i += 1

        i += 1  # past ']'
        if len(bracket_tokens) == 1 and bracket_tokens[0].type == "STRING":
            content, quote = self._extract_string_content(bracket_tokens[0].value)
            return LuaString(content, quote), i
        if len(bracket_tokens) == 1 and bracket_tokens[0].type == "IDENT":
            # Like [HITGROUP_HEAD]
            return LuaRaw(bracket_tokens[0].value), i

        return LuaRaw("".join(t.value for t in bracket_tokens)), i

    def _parse_call_args(self, start: int) -> Tuple[List[str], int]:
        """Parses comma-separated arguments inside `( ... )`"""
        i = start
        depth = 1
        cur_arg: List[str] = []
        args: List[str] = []

        while i < len(self.tokens) and depth > 0:
            t = self.tokens[i]
            if t.value == '(':
                depth += 1
                cur_arg.append(t.value)
            elif t.value == ')':
                depth -= 1
                if depth == 0:
                    if cur_arg:
                        args.append(" ".join(cur_arg))
                    break
                else:
                    cur_arg.append(t.value)
            elif t.value == ',' and depth == 1:
                args.append(" ".join(cur_arg))
                cur_arg = []
            else:
                cur_arg.append(t.value)
            i += 1

        return args, i + 1

    def _extract_expression_chain(self, start: int) -> Tuple[str, int]:
        """Extracts an arbitrary expression until a comma, semicolon, closing bracket, or newline"""
        i = start
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0
        expr_tokens: List[str] = []
        start_line = self.tokens[start].line

        while i < len(self.tokens):
            t = self.tokens[i]

            if paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
                if t.type == "COMMENT":
                    break
                if t.line > start_line:
                    break
                if t.value in (',', ';'):
                    break
                # Check for start of next statement: IDENT followed by '=' or 'function'
                if i > start and t.type == "IDENT":
                    target, eq_pos, _ = self._check_assignment_target(i)
                    if target and eq_pos is not None:
                        break
                    if t.value in ("function", "local"):
                        break

            if t.value in ('(', '{', '['):
                if t.value == '(':
                    paren_depth += 1
                elif t.value == '{':
                    brace_depth += 1
                elif t.value == '[':
                    bracket_depth += 1
            elif t.value in (')', '}', ']'):
                if paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
                    break
                if t.value == ')':
                    paren_depth -= 1
                elif t.value == '}':
                    brace_depth -= 1
                elif t.value == ']':
                    bracket_depth -= 1

            if t.type != "COMMENT":
                expr_tokens.append(t.value)
            i += 1

        return " ".join(expr_tokens), i

    def _extract_function_block(self, start: int) -> Tuple[str, int]:
        """Extracts a function ... end block"""
        i = start
        depth = 0
        tokens_in_func: List[Token] = []

        while i < len(self.tokens):
            t = self.tokens[i]
            tokens_in_func.append(t)
            if t.type == "IDENT" and t.value in ("function", "if", "do"):
                depth += 1
            elif t.type == "IDENT" and t.value == "end":
                depth -= 1
                if depth <= 0:
                    i += 1
                    break
            i += 1

        return self._slice_tokens(start, i), i

    def _extract_raw_statement(self, start: int) -> Tuple[str, int]:
        """Extracts a raw statement until newline or next statement boundary"""
        i = start
        parts: List[Token] = []
        cur_line = self.tokens[start].line

        while i < len(self.tokens):
            t = self.tokens[i]
            if i > start and t.line > cur_line:
                # Check if next token starts a new statement
                target, eq_pos, _ = self._check_assignment_target(i)
                if (target and eq_pos is not None) or (t.type == "IDENT" and t.value in ("function", "local")):
                    break
            parts.append(t)
            cur_line = t.line
            i += 1

        return self._slice_tokens(start, i), i

    def _slice_tokens(self, start: int, end: int) -> str:
        """Reconstructs text between token indices start and end from raw text"""
        if start >= len(self.tokens):
            return ""
        if end > len(self.tokens):
            end = len(self.tokens)
        first_tok = self.tokens[start]
        last_tok = self.tokens[end - 1]

        # Use token positions
        first_line = first_tok.line
        first_col = first_tok.col
        # Find offset in text
        lines = self.text.splitlines(keepends=True)
        start_offset = sum(len(l) for l in lines[:first_line-1]) + (first_col - 1)

        last_line = last_tok.line
        last_col = last_tok.col
        end_offset = sum(len(l) for l in lines[:last_line-1]) + (last_col - 1) + len(last_tok.value)

        return self.text[start_offset:end_offset]

    def _peek_sym(self, idx: int, sym: str) -> bool:
        return idx < len(self.tokens) and self.tokens[idx].type == "SYMBOL" and self.tokens[idx].value == sym

    def _extract_string_content(self, s: str) -> Tuple[str, str]:
        if s.startswith('[[') and s.endswith(']]'):
            return s[2:-2], '[['
        bracket_match = re.match(r'^\[(=*)\[(.*)\]\1\]$', s, re.DOTALL)
        if bracket_match:
            return bracket_match.group(2), f'[{bracket_match.group(1)}['
        quote = s[0]
        inner = s[1:-1]
        # Basic unescape
        inner = inner.replace(f'\\{quote}', quote).replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
        return inner, quote
