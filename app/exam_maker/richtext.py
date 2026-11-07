"""Formatted text: Excel rich text and **tag** markup -> a list of styled runs.

Tags: **bold**, *italic*, __underline__, ~subscript~, ^superscript^.
A tag with no closing partner is kept as literal text.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from openpyxl.cell.rich_text import CellRichText, TextBlock


@dataclass(frozen=True)
class Run:
    text: str
    b: bool = False
    i: bool = False
    u: bool = False
    sub: bool = False
    sup: bool = False

    def same_style(self, other: "Run") -> bool:
        return (self.b, self.i, self.u, self.sub, self.sup) == (other.b, other.i, other.u, other.sub, other.sup)


# Longest markers first so "**" wins over "*".
_TAGS = (("**", "b"), ("__", "u"), ("*", "i"), ("~", "sub"), ("^", "sup"))


def parse_tags(text: str, base: Run | None = None) -> list[Run]:
    base = base or Run("")
    runs: list[Run] = []
    buf = ""
    i = 0
    while i < len(text):
        for tok, attr in _TAGS:
            if not text.startswith(tok, i):
                continue
            start = i + len(tok)
            end = text.find(tok, start)
            inner = text[start:end] if end != -1 else ""
            if end == -1 or not inner.strip():
                continue
            if buf:
                runs.append(replace(base, text=buf))
                buf = ""
            runs.extend(parse_tags(inner, replace(base, **{attr: True})))
            i = end + len(tok)
            break
        else:
            buf += text[i]
            i += 1
    if buf:
        runs.append(replace(base, text=buf))
    return merge(runs)


def merge(runs: list[Run]) -> list[Run]:
    out: list[Run] = []
    for r in runs:
        if not r.text:
            continue
        if out and out[-1].same_style(r):
            out[-1] = replace(out[-1], text=out[-1].text + r.text)
        else:
            out.append(r)
    return out


def cell_to_text(value) -> str:
    """Plain string for a non-rich cell value (whole-number floats print without .0)."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _font_base(font) -> Run:
    if font is None:
        return Run("")
    va = getattr(font, "vertAlign", None)
    return Run("", b=bool(font.b), i=bool(font.i), u=bool(font.u) and font.u != "none",
               sub=va == "subscript", sup=va == "superscript")


def from_cell(cell) -> list[Run]:
    """Runs for an openpyxl cell loaded with rich_text=True."""
    value = cell.value
    base = _font_base(cell.font)
    if isinstance(value, CellRichText):
        runs: list[Run] = []
        for block in value:
            if isinstance(block, TextBlock):
                f = block.font
                va = f.vertAlign if f.vertAlign is not None else ("subscript" if base.sub else "superscript" if base.sup else None)
                b = Run("",
                        b=base.b if f.b is None else bool(f.b),
                        i=base.i if f.i is None else bool(f.i),
                        u=base.u if f.u is None else (bool(f.u) and f.u != "none"),
                        sub=va == "subscript", sup=va == "superscript")
                runs.extend(parse_tags(block.text, b))
            else:
                runs.extend(parse_tags(str(block), base))
        return merge(runs)
    return parse_tags(cell_to_text(value).strip(), base)


def plain(runs: list[Run]) -> str:
    return "".join(r.text for r in runs)


def to_tags(runs: list[Run]) -> str:
    """Serialize runs back to tag markup (used in the Form Key CSV)."""
    out = []
    for r in runs:
        t = r.text
        if r.sub:
            t = f"~{t}~"
        if r.sup:
            t = f"^{t}^"
        if r.u:
            t = f"__{t}__"
        if r.i:
            t = f"*{t}*"
        if r.b:
            t = f"**{t}**"
        out.append(t)
    return "".join(out)
