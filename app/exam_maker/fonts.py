"""Georgia for exam text, with two per-character substitutions:

- Digits use Times New Roman, because Georgia's old-style numerals make 0 look like o and 1 look short.
- Symbols Georgia lacks use Arial Unicode.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

REGULAR, BOLD, ITALIC, BOLD_ITALIC = "Georgia", "Georgia-Bold", "Georgia-Italic", "Georgia-BoldItalic"
DIGITS = "ExamDigits"
FALLBACK = "ExamFallback"
WORD_FONT = "Georgia"
WORD_DIGIT_FONT = "Times New Roman"

MAIN, DIGIT, SYMBOL = "main", "digit", "symbol"

_DIRS = [Path("/System/Library/Fonts/Supplemental"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"]
_FILES = {REGULAR: "Georgia.ttf", BOLD: "Georgia Bold.ttf", ITALIC: "Georgia Italic.ttf",
          BOLD_ITALIC: "Georgia Bold Italic.ttf"}
_DIGIT_FILES = {DIGITS: "Times New Roman.ttf", f"{DIGITS}-Bold": "Times New Roman Bold.ttf",
                f"{DIGITS}-Italic": "Times New Roman Italic.ttf",
                f"{DIGITS}-BoldItalic": "Times New Roman Bold Italic.ttf"}
_FALLBACK_FILES = ["Arial Unicode.ttf", "Arial.ttf"]

_registered = False
_has_digits = False
_has_fallback = False
_georgia_chars: frozenset[int] = frozenset()


def _find(name: str) -> Path | None:
    return next((d / name for d in _DIRS if (d / name).is_file()), None)


def register_fonts() -> None:
    global _registered, _georgia_chars, _has_digits, _has_fallback
    if _registered:
        return
    for font_name, file in _FILES.items():
        path = _find(file)
        if path is None:
            raise FileNotFoundError(f"Font '{file}' not found. Georgia ships with macOS in /System/Library/Fonts/Supplemental.")
        pdfmetrics.registerFont(TTFont(font_name, str(path)))
    pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD, italic=ITALIC, boldItalic=BOLD_ITALIC)

    digit_paths = {name: _find(file) for name, file in _DIGIT_FILES.items()}
    if all(digit_paths.values()):
        for name, path in digit_paths.items():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        pdfmetrics.registerFontFamily(DIGITS, normal=DIGITS, bold=f"{DIGITS}-Bold", italic=f"{DIGITS}-Italic",
                                      boldItalic=f"{DIGITS}-BoldItalic")
        _has_digits = True

    fb = next((p for p in map(_find, _FALLBACK_FILES) if p), None)
    if fb:
        pdfmetrics.registerFont(TTFont(FALLBACK, str(fb)))
        for b in (0, 1):
            for i in (0, 1):
                addMapping(FALLBACK, b, i, FALLBACK)
        _has_fallback = True
    _georgia_chars = frozenset(pdfmetrics.getFont(REGULAR).face.charToGlyph)
    _registered = True


def digit_font(bold: bool = False, italic: bool = False) -> str:
    """ReportLab font name for digits in the given style (Georgia if Times New Roman is missing)."""
    register_fonts()
    if not _has_digits:
        return {(0, 0): REGULAR, (1, 0): BOLD, (0, 1): ITALIC, (1, 1): BOLD_ITALIC}[(bold, italic)]
    return DIGITS + {(0, 0): "", (1, 0): "-Bold", (0, 1): "-Italic", (1, 1): "-BoldItalic"}[(bold, italic)]


def char_kind(ch: str) -> str:
    register_fonts()
    if "0" <= ch <= "9":
        return DIGIT if _has_digits else MAIN
    if ch in "\n\t " or ord(ch) in _georgia_chars or not _has_fallback:
        return MAIN
    return SYMBOL


def segments(text: str) -> list[tuple[str, str]]:
    """Split text into (kind, chunk) pieces: MAIN (Georgia), DIGIT (Times New Roman) or SYMBOL (fallback)."""
    out: list[tuple[str, str]] = []
    for ch in text:
        kind = char_kind(ch)
        if out and out[-1][0] == kind:
            out[-1] = (kind, out[-1][1] + ch)
        else:
            out.append((kind, ch))
    return out
