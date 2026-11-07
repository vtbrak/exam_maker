"""Render a form (or its answer key) to PDF with ReportLab."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Image as RLImage, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import CHOICE_LETTERS
from .builder import Block, Form, PrintedQuestion
from .fonts import DIGIT, FALLBACK, REGULAR, SYMBOL, digit_font, register_fonts, segments
from .images import fit_size, load_image
from .layout import PAGE_H, PAGE_W, ExamInfo, choices_inline, set_intro
from .richtext import Run

HIGHLIGHT = "#FFF176"
FRAME_PAD = 6        # ReportLab's default body-frame padding; the page header lines up with the body text
_NO_PAD = [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
           ("VALIGN", (0, 0), (-1, -1), "TOP")]


def _text(s: str, b: bool = False, i: bool = False) -> str:
    """Escape text, routing digits to Times New Roman and symbols Georgia lacks to the fallback font.

    b/i must match the surrounding <b>/<i> tags: ReportLab doesn't carry them into a <font name=...>.
    """
    out = []
    for kind, chunk in segments(s):
        t = escape(chunk).replace("\n", "<br/>")
        if kind == DIGIT:
            t = f'<font name="{digit_font(b, i)}">{t}</font>'
        elif kind == SYMBOL:
            t = f'<font name="{FALLBACK}">{t}</font>'
        out.append(t)
    return "".join(out)


def _draw(canvas, x: float, y: float, text: str, size: float, align_right: bool = False) -> None:
    """Draw one line on the canvas with the same font substitutions as body text."""
    fonts = {DIGIT: digit_font(), SYMBOL: FALLBACK}
    parts = [(fonts.get(kind, REGULAR), chunk) for kind, chunk in segments(text)]
    if align_right:
        x -= sum(canvas.stringWidth(c, f, size) for f, c in parts)
    for font, chunk in parts:
        canvas.setFont(font, size)
        canvas.drawString(x, y, chunk)
        x += canvas.stringWidth(chunk, font, size)


def markup(runs: list[Run], bold: bool = False) -> str:
    parts = []
    for r in runs:
        b = r.b or bold
        t = _text(r.text, b, r.i)
        if r.sub:
            t = f"<sub>{t}</sub>"
        if r.sup:
            t = f"<super>{t}</super>"
        if r.u:
            t = f"<u>{t}</u>"
        if r.i:
            t = f"<i>{t}</i>"
        if b:
            t = f"<b>{t}</b>"
        parts.append(t)
    return "".join(parts)


class _Styles:
    def __init__(self, info: ExamInfo):
        fs = info.font_size
        lead = fs * 1.28
        self.body = ParagraphStyle("body", fontName=REGULAR, fontSize=fs, leading=lead)
        self.num = ParagraphStyle("num", parent=self.body)
        self.title = ParagraphStyle("title", parent=self.body, fontSize=fs + 5, leading=(fs + 5) * 1.2)
        self.form = ParagraphStyle("form", parent=self.title, alignment=TA_RIGHT)
        self.instr = ParagraphStyle("instr", parent=self.body, fontSize=fs - 0.5, leading=(fs - 0.5) * 1.3)
        self.intro = ParagraphStyle("intro", parent=self.body)
        self.version = ParagraphStyle("version", parent=self.body, fontSize=fs - 2.5, leading=(fs - 2.5) * 1.3,
                                      textColor=colors.HexColor("#6B6B6B"))
        self.q_gap = fs * 0.85          # space after each question
        self.choice_gap = fs * 0.12     # space between stacked choices


def _image(path: Path, pct: int | None, info: ExamInfo, space: float) -> list:
    img = load_image(path)
    w, h = fit_size(img, pct, PAGE_H, info.content_width)
    flow = RLImage(str(img.embed_path), width=w, height=h)
    flow.hAlign = "CENTER"
    return [flow, Spacer(1, space)]


def _choice_text(runs: list[Run], is_key: bool) -> str:
    return f'<span backColor="{HIGHLIGHT}">{markup(runs, bold=True)}</span>' if is_key else markup(runs)


def _question(q: PrintedQuestion, info: ExamInfo, st: _Styles, key: bool, show_image: bool) -> list:
    fs = info.font_size
    flows: list = []
    if show_image and q.slot.image:
        flows += _image(q.slot.image, q.slot.image_pct, info, fs * 0.5)

    stem = Table([[Paragraph(f"<b>{_text(f'{q.number}.', b=True)}</b>", st.num), Paragraph(markup(q.alt.question), st.body)]],
                 colWidths=[info.num_indent, info.content_width - info.num_indent])
    stem.setStyle(TableStyle(_NO_PAD + [("BOTTOMPADDING", (0, 0), (-1, -1), fs * 0.3)]))
    flows.append(stem)

    choices = q.choices
    correct = q.order.index(0)
    if choices_inline(choices, info):
        cell = (info.content_width - info.num_indent) / len(choices)
        row = [""] + [Paragraph(f"{CHOICE_LETTERS[p]})&nbsp;&nbsp;{_choice_text(c, key and p == correct)}", st.body)
                      for p, c in enumerate(choices)]
        t = Table([row], colWidths=[info.num_indent] + [cell] * len(choices))
        t.setStyle(TableStyle(_NO_PAD))
    else:
        rows = [["", Paragraph(f"{CHOICE_LETTERS[p]})", st.body), Paragraph(_choice_text(c, key and p == correct), st.body)]
                for p, c in enumerate(choices)]
        t = Table(rows, colWidths=[info.num_indent, info.letter_indent,
                                   info.content_width - info.num_indent - info.letter_indent])
        t.setStyle(TableStyle(_NO_PAD + [("BOTTOMPADDING", (0, 0), (-1, -1), st.choice_gap)]))
    flows += [t, Spacer(1, st.q_gap)]
    return flows


def _block(block: Block, info: ExamInfo, st: _Styles, key: bool) -> list:
    qs = block.questions
    if block.image_slot is None and not block.intro:
        return [KeepTogether(_question(q, info, st, key, show_image=not block.linked_set)) for q in qs]
    if block.intro:
        head = [Paragraph(markup(block.intro), st.body), Spacer(1, info.font_size * 0.5)]
    else:
        head = [Paragraph(f"<i>{_text(set_intro(qs[0].number, qs[-1].number), i=True)}</i>", st.intro),
                Spacer(1, info.font_size * 0.4)]
    if block.image_slot is not None:
        head += _image(block.image_slot.image, block.image_slot.image_pct, info, info.font_size * 0.6)
    flows = [KeepTogether(head + _question(qs[0], info, st, key, show_image=False))]
    flows += [KeepTogether(_question(q, info, st, key, show_image=False)) for q in qs[1:]]
    return flows


def _page_header(form: Form, info: ExamInfo, st: _Styles, label: str) -> Table:
    """Title + form letter and version (small, grey); drawn at the top of every page."""
    fs, cw = info.font_size, info.content_width - 2 * FRAME_PAD
    right = f"{label} · Form {form.letter}" if label else f"Form {form.letter}"
    right_w = min(stringWidth(right, "Georgia-Bold", st.form.fontSize) + fs, cw * 0.6)   # fit the label on one line
    top = Table([[Paragraph(f"<b>{_text(info.title, b=True)}</b>", st.title), Paragraph(f"<b>{_text(right, b=True)}</b>", st.form)]],
                colWidths=[cw - right_w, right_w])
    top.setStyle(TableStyle(_NO_PAD + [("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    rows = [[top]]
    if info.version:
        rows.append([Paragraph(_text(f"Version {info.version}"), st.version)])
    header = Table(rows, colWidths=[cw])
    header.setStyle(TableStyle(_NO_PAD))
    header.wrap(cw, PAGE_H)
    return header


def _first_page(info: ExamInfo, st: _Styles) -> list:
    """Page 1 only, between the header and question 1: the Name line and the instructions."""
    fs = info.font_size
    name = Table([[Paragraph("<b>Name:</b>", st.num), ""]], colWidths=[fs * 4, info.content_width * 0.6])
    name.hAlign = "LEFT"
    name.setStyle(TableStyle(_NO_PAD + [("LINEBELOW", (1, 0), (1, 0), 0.8, colors.black),
                                        ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    flows = [name, Spacer(1, fs * 1.2)]
    if info.instructions.strip():
        flows += [Paragraph(_text(info.instructions.strip()), st.instr), Spacer(1, fs * 1.0)]
    return flows


def _canvas_class(footer_left: str):
    class NumberedCanvas(rl_canvas.Canvas):
        """Two-pass canvas so the footer can say 'Page X of Y'."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self.setFillColor(colors.HexColor("#444444"))
                y = 0.45 * 72
                _draw(self, self._margin, y, footer_left, 9)
                _draw(self, PAGE_W - self._margin, y, f"Page {self._pageNumber} of {total}", 9, align_right=True)
                super().showPage()
            super().save()

    return NumberedCanvas


def render_pdf(form: Form, info: ExamInfo, path: Path, key: bool = False, label: str = "") -> None:
    """label: extra header text such as 'ANSWER KEY' or 'DRAFT PREVIEW'."""
    register_fonts()
    st = _Styles(info)
    header = _page_header(form, info, st, label)
    header_h = header._height

    def draw_header(canvas, _doc):
        header.drawOn(canvas, info.margin + FRAME_PAD, PAGE_H - info.margin - header_h)

    doc = SimpleDocTemplate(str(path), pagesize=(PAGE_W, PAGE_H), leftMargin=info.margin, rightMargin=info.margin,
                            topMargin=info.margin + header_h + info.font_size * 0.9,
                            bottomMargin=max(info.margin, 0.8 * 72),
                            title=f"{info.title} - Form {form.letter}" + (f" ({label})" if label else ""))
    story = _first_page(info, st)
    for block in form.blocks:
        story += _block(block, info, st, key)
    footer = f"Form {form.letter}" + (f" · {label}" if label else "")
    canvas_cls = _canvas_class(footer)
    canvas_cls._margin = info.margin
    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header, canvasmaker=canvas_cls)
