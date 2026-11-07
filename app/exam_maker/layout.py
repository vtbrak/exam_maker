"""Page settings and layout decisions shared by the PDF and Word renderers."""
from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth

from .fonts import BOLD, register_fonts
from .richtext import Run, plain

PAGE_W, PAGE_H = letter          # points; 612 x 792


@dataclass
class ExamInfo:
    title: str
    instructions: str
    font_size: float = 11.0
    margin_in: float = 0.75
    version: str = ""                  # 6-digit semester code from the bank's file name, printed under the title

    @property
    def margin(self) -> float:
        return self.margin_in * 72

    @property
    def content_width(self) -> float:
        return PAGE_W - 2 * self.margin

    @property
    def num_indent(self) -> float:        # width of the "12." column
        return self.font_size * 2.3

    @property
    def letter_indent(self) -> float:     # width of the "A)" column
        return self.font_size * 1.9


def choices_inline(choices: list[list[Run]], info: ExamInfo) -> bool:
    """True when every choice is short enough to print side by side on one line."""
    register_fonts()
    avail = info.content_width - info.num_indent
    cell = avail / len(choices)
    pad = info.font_size * 1.2
    return all(stringWidth(plain(c), BOLD, info.font_size) + info.letter_indent + pad <= cell for c in choices)


def set_intro(first: int, last: int) -> str:
    """Default line above a linked set's figure when the set has no Set Intro of its own."""
    if first == last:
        return f"Use the figure below to answer question {first}."
    return f"Use the figure below to answer questions {first}–{last}."
