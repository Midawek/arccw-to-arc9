"""
Lua Tokenizer for GMod Lua (ArcCW & ARC9)
Handles GMod dialect features (// comments, /* */ comments, !=, &&, ||, +=, etc.)
"""
import re
from typing import List, NamedTuple, Optional

class Token(NamedTuple):
    type: str
    value: str
    line: int
    col: int

class LuaTokenizer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(text)

    def tokenize(self, include_comments: bool = False, include_whitespace: bool = False) -> List[Token]:
        tokens = []
        while self.pos < self.length:
            start_pos = self.pos
            start_line = self.line
            start_col = self.col
            ch = self.text[self.pos]

            # Whitespace
            if ch in ' \t\r\n':
                ws = []
                while self.pos < self.length and self.text[self.pos] in ' \t\r\n':
                    c = self.text[self.pos]
                    ws.append(c)
                    if c == '\n':
                        self.line += 1
                        self.col = 1
                    else:
                        self.col += 1
                    self.pos += 1
                if include_whitespace:
                    tokens.append(Token("WHITESPACE", "".join(ws), start_line, start_col))
                continue

            # Comments: -- or // or /* */
            if self.pos + 1 < self.length and self.text[self.pos:self.pos+2] == '--':
                # Check for long bracket comment: --[=[ ... ]=]
                self.pos += 2
                self.col += 2
                bracket_match = re.match(r'^\[(=*)\[', self.text[self.pos:])
                if bracket_match:
                    equals = bracket_match.group(1)
                    close_tag = f']{equals}]'
                    close_idx = self.text.find(close_tag, self.pos + len(bracket_match.group(0)))
                    if close_idx != -1:
                        comment_content = self.text[start_pos : close_idx + len(close_tag)]
                        self._advance_through(close_idx + len(close_tag) - self.pos)
                    else:
                        comment_content = self.text[start_pos:]
                        self._advance_through(self.length - self.pos)
                else:
                    # Single-line comment until newline
                    nl = self.text.find('\n', self.pos)
                    if nl != -1:
                        comment_content = self.text[start_pos:nl]
                        self._advance_through(nl - self.pos)
                    else:
                        comment_content = self.text[start_pos:]
                        self._advance_through(self.length - self.pos)
                if include_comments:
                    tokens.append(Token("COMMENT", comment_content, start_line, start_col))
                continue

            # GMod C-style single-line comment: //
            if self.pos + 1 < self.length and self.text[self.pos:self.pos+2] == '//':
                nl = self.text.find('\n', self.pos)
                if nl != -1:
                    comment_content = self.text[start_pos:nl]
                    self._advance_through(nl - self.pos)
                else:
                    comment_content = self.text[start_pos:]
                    self._advance_through(self.length - self.pos)
                if include_comments:
                    tokens.append(Token("COMMENT", comment_content, start_line, start_col))
                continue

            # GMod C-style block comment: /* ... */
            if self.pos + 1 < self.length and self.text[self.pos:self.pos+2] == '/*':
                close_idx = self.text.find('*/', self.pos + 2)
                if close_idx != -1:
                    comment_content = self.text[start_pos : close_idx + 2]
                    self._advance_through(close_idx + 2 - self.pos)
                else:
                    comment_content = self.text[start_pos:]
                    self._advance_through(self.length - self.pos)
                if include_comments:
                    tokens.append(Token("COMMENT", comment_content, start_line, start_col))
                continue

            # Strings: single quote, double quote, or long brackets
            if ch in ('"', "'"):
                quote = ch
                self.pos += 1
                self.col += 1
                val = [quote]
                escaped = False
                while self.pos < self.length:
                    c = self.text[self.pos]
                    val.append(c)
                    self.pos += 1
                    self.col += 1
                    if c == '\n':
                        self.line += 1
                        self.col = 1
                    if escaped:
                        escaped = False
                    elif c == '\\':
                        escaped = True
                    elif c == quote:
                        break
                tokens.append(Token("STRING", "".join(val), start_line, start_col))
                continue

            # Long bracket strings: [=[ ... ]=]
            bracket_match = re.match(r'^\[(=*)\[', self.text[self.pos:])
            if bracket_match:
                equals = bracket_match.group(1)
                close_tag = f']{equals}]'
                open_len = len(bracket_match.group(0))
                close_idx = self.text.find(close_tag, self.pos + open_len)
                if close_idx != -1:
                    end_idx = close_idx + len(close_tag)
                    content = self.text[self.pos : end_idx]
                    self._advance_through(end_idx - self.pos)
                else:
                    content = self.text[self.pos:]
                    self._advance_through(self.length - self.pos)
                tokens.append(Token("STRING", content, start_line, start_col))
                continue

            # Numbers
            # Decimal, hex (0x...), float
            num_match = re.match(r'^(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)', self.text[self.pos:])
            if num_match:
                val = num_match.group(0)
                self._advance_through(len(val))
                tokens.append(Token("NUMBER", val, start_line, start_col))
                continue

            # Identifiers / Keywords
            ident_match = re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*', self.text[self.pos:])
            if ident_match:
                val = ident_match.group(0)
                self._advance_through(len(val))
                tokens.append(Token("IDENT", val, start_line, start_col))
                continue

            # Multi-character symbols
            # .., ..., ==, ~=, !=, <=, >=, &&, ||, +=, -=, *=, /=
            for sym in ['...', '..', '==', '~=', '!=', '<=', '>=', '&&', '||', '+=', '-=', '*=', '/=']:
                if self.text.startswith(sym, self.pos):
                    self._advance_through(len(sym))
                    tokens.append(Token("SYMBOL", sym, start_line, start_col))
                    break
            else:
                # Single-character symbol
                sym = self.text[self.pos]
                self._advance_through(1)
                tokens.append(Token("SYMBOL", sym, start_line, start_col))

        return tokens

    def _advance_through(self, count: int):
        for _ in range(count):
            if self.pos < self.length:
                if self.text[self.pos] == '\n':
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
                self.pos += 1
