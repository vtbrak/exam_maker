"""Render a student form to Word (.docx). Close to the PDF, but the PDF is the print master."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from . import CHOICE_LETTERS
from .builder import Form, PrintedQuestion
from .fonts import DIGIT, WORD_DIGIT_FONT, WORD_FONT, segments
from .images import fit_size, load_image
from .layout import PAGE_H, PAGE_W, ExamInfo, choices_inline, set_intro
from .richtext import Run


def _add(par, text: str, style: Run | None = None, size: float | None = None) -> list:
    """Add text as Word runs; digits get Times New Roman (Georgia's old-style 0 looks like o)."""
    style = style or Run("")
    added = []
    lines = text.split("\n")
    for n, line in enumerate(lines):
        for kind, chunk in segments(line):
            run = par.add_run(chunk)
            run.bold, run.italic, run.underline = style.b, style.i, style.u
            run.font.subscript, run.font.superscript = style.sub, style.sup
            if kind == DIGIT:
                run.font.name = WORD_DIGIT_FONT
            if size:
                run.font.size = Pt(size)
            added.append(run)
        if n < len(lines) - 1:
            (added[-1] if added else par.add_run()).add_break()
    return added


def _runs(par, runs: list[Run]):
    for r in runs:
        _add(par, r.text, r)


def _fmt(par, before=0.0, after=0.0, keep_next=False):
    pf = par.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.keep_with_next = keep_next
    pf.keep_together = True
    return pf


def _field(par, instr: str):
    run = par.add_run()
    run.font.name = WORD_DIGIT_FONT
    for tag, attrs, text in (("w:fldChar", {"w:fldCharType": "begin"}, None),
                             ("w:instrText", {"xml:space": "preserve"}, instr),
                             ("w:fldChar", {"w:fldCharType": "separate"}, None),
                             ("w:t", {}, "1"),
                             ("w:fldChar", {"w:fldCharType": "end"}, None)):
        el = OxmlElement(tag)
        for k, v in attrs.items():
            el.set(qn(k), v)
        if text is not None:
            el.text = text
        run._r.append(el)
    return run


def _image(doc, path: Path, pct: int | None, info: ExamInfo, after: float):
    img = load_image(path)
    w, h = fit_size(img, pct, PAGE_H, info.content_width)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _fmt(par, after=after, keep_next=True)
    par.add_run().add_picture(str(img.embed_path), width=Pt(w), height=Pt(h))


def _question(doc, q: PrintedQuestion, info: ExamInfo, show_image: bool):
    fs = info.font_size
    if show_image and q.slot.image:
        _image(doc, q.slot.image, q.slot.image_pct, info, fs * 0.5)

    stem = doc.add_paragraph()
    pf = _fmt(stem, after=fs * 0.3, keep_next=True)
    pf.left_indent = Pt(info.num_indent)
    pf.first_line_indent = Pt(-info.num_indent)
    pf.tab_stops.add_tab_stop(Pt(info.num_indent))
    _add(stem, f"{q.number}.\t", Run("", b=True))
    _runs(stem, q.alt.question)

    choices = q.choices
    if choices_inline(choices, info):
        par = doc.add_paragraph()
        pf = _fmt(par, after=fs * 0.85)
        pf.left_indent = Pt(info.num_indent)
        cell = (info.content_width - info.num_indent) / len(choices)
        for p in range(1, len(choices)):
            pf.tab_stops.add_tab_stop(Pt(info.num_indent + cell * p), WD_TAB_ALIGNMENT.LEFT)
        for p, c in enumerate(choices):
            par.add_run(("\t" if p else "") + f"{CHOICE_LETTERS[p]})  ")
            _runs(par, c)
        return

    indent = info.num_indent + info.letter_indent
    for p, c in enumerate(choices):
        last = p == len(choices) - 1
        par = doc.add_paragraph()
        pf = _fmt(par, after=fs * 0.85 if last else fs * 0.12, keep_next=not last)
        pf.left_indent = Pt(indent)
        pf.first_line_indent = Pt(-info.letter_indent)
        pf.tab_stops.add_tab_stop(Pt(indent))
        par.add_run(f"{CHOICE_LETTERS[p]})\t")
        _runs(par, c)


def render_docx(form: Form, info: ExamInfo, path: Path) -> None:
    fs = info.font_size
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Pt(PAGE_W), Pt(PAGE_H)
    sec.left_margin = sec.right_margin = Pt(info.margin)
    sec.header_distance = Pt(info.margin)
    sec.top_margin = Pt(info.margin + fs * (3.6 if info.version else 2.6))   # room for the page header
    sec.bottom_margin = Pt(max(info.margin, 0.8 * 72))
    sec.footer_distance = Pt(0.45 * 72)

    normal = doc.styles["Normal"]
    normal.font.name = WORD_FONT
    normal.font.size = Pt(fs)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), WORD_FONT)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.1

    # Page header (every page): title + form letter, version (small, grey).
    hdr = sec.header
    top = hdr.paragraphs[0]
    _fmt(top)
    top.paragraph_format.tab_stops.add_tab_stop(Pt(info.content_width), WD_TAB_ALIGNMENT.RIGHT)
    _add(top, f"{info.title}\tForm {form.letter}", Run("", b=True), size=fs + 5)
    if info.version:
        ver = hdr.add_paragraph()
        _fmt(ver)
        for run in _add(ver, f"Version {info.version}", size=fs - 2.5):
            run.font.color.rgb = RGBColor(0x6B, 0x6B, 0x6B)

    # Page 1 only: Name line, then instructions.
    name = doc.add_paragraph()
    _fmt(name, after=fs * 1.2)
    name.add_run("Name: ").bold = True
    name.add_run("_" * 45)

    if info.instructions.strip():
        ins = doc.add_paragraph()
        _fmt(ins, after=fs * 1.0)
        _add(ins, info.instructions.strip(), size=fs - 0.5)

    for block in form.blocks:
        qs = block.questions
        if block.intro or block.image_slot is not None:
            intro = doc.add_paragraph()
            _fmt(intro, after=fs * 0.5, keep_next=True)
            if block.intro:
                _runs(intro, block.intro)
            else:
                _add(intro, set_intro(qs[0].number, qs[-1].number), Run("", i=True))
        if block.image_slot is not None:
            _image(doc, block.image_slot.image, block.image_slot.image_pct, info, fs * 0.6)
        for q in qs:
            _question(doc, q, info, show_image=not block.linked_set)

    # Footer: "Form A" left, "Page X of Y" right.
    fpar = sec.footer.paragraphs[0]
    fpar.paragraph_format.tab_stops.add_tab_stop(Pt(info.content_width), WD_TAB_ALIGNMENT.RIGHT)
    fpar.add_run(f"Form {form.letter}\tPage ")
    _field(fpar, "PAGE")
    fpar.add_run(" of ")
    _field(fpar, "NUMPAGES")
    for run in fpar.runs:
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    doc.save(str(path))

