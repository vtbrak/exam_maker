"""Scantron key sheets: the Exam Scanner's answer sheet with each form's key bubbled in.

Spec: 'Scantron Key Sheets.md' (exam maker folder). One PDF, three pages (Forms A, B, C), scanned in the
Exam Scanner's key-check mode. The filled letters come from the Mapping CSV rows of the same run.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas

from . import CHOICE_LETTERS, FORM_LETTERS, QUESTIONS_PER_EXAM

# --------------------------------------------------------------------------------------------------------------
# SHEET_TEMPLATE mirrors the Exam Scanner's sheet: `Exam scanner/app/engine.js` (TPL) and `app/pdfgen.js`
# (sheetPage), as of 2026-10-07. IF EITHER SIDE CHANGES, CHANGE BOTH (see 'Scantron Key Sheets.md' section 7).
# Units: PDF points; origin TOP-LEFT, y increasing downward (converted to ReportLab's bottom-left when drawn).
# --------------------------------------------------------------------------------------------------------------
SHEET_TEMPLATE = {
    "page": (612.0, 792.0),
    "large_square": 11.1,
    "large_squares": [(155.55, 188.15), (456.45, 188.15), (155.55, 396.05), (456.45, 396.05),
                      (155.55, 603.85), (456.45, 603.85)],
    "small_square": 7.8,
    "small_squares": [(306.0, 213.4), (306.0, 402.0), (306.0, 606.1)],
    "left_cols": [197.7, 212.7, 227.7, 242.7, 257.7],     # x of A..E
    "right_cols": [290.7, 305.7, 320.7, 335.7, 350.7],
    "row_step": 20.0,
    "q1_y": 231.13,       # questions 1-8, left block
    "q9_y": 419.72,       # questions 9-17, left block
    "q18_y": 231.13,      # questions 18-25, right block
    "filled_r": 5.6,
    "empty_r": 6.0,
    "empty_grey": 0.6,    # 60% grey outline
    "empty_line": 0.5,
    "bubble_font": 6.0,
    "qnum_font": 9.0,
    "qnum_gap": 8.5,      # number ends this far left of the A bubble
    "qnum_baseline": 3.2,
    "form_bubbles": [(284.72, 588.31), (299.72, 588.31), (314.72, 588.31)],   # A, B, C
    "form_label": (299.7, 575.0),
    "form_box": (275.7, 578.3, 48.0, 20.0),
    "id_cols": 7,
    "id_bubble": (341.22, 15.0, 427.31, 18.0),      # x0, dx per column, y0, dy per digit
    "id_label": (333.7, 395.0),
    "id_box": (333.7, 398.3, 105.0, 200.0),
    "id_write_row": 20.0,
    "name_label": (172.2, 179.0),
    "name_box": (172.2, 182.6, 144.0, 23.0),
    "name_text": (176.0, 197.5),
    "footer": (150.0, 640.0),
}
T = SHEET_TEMPLATE
PAGE_H = T["page"][1]


def bubble_center(question: int, letter: str) -> tuple[float, float]:
    """Top-left-origin centre of a question's answer bubble."""
    i = CHOICE_LETTERS.index(letter)
    if 1 <= question <= 8:
        return T["left_cols"][i], T["q1_y"] + T["row_step"] * (question - 1)
    if 9 <= question <= 17:
        return T["left_cols"][i], T["q9_y"] + T["row_step"] * (question - 9)
    if 18 <= question <= 25:
        return T["right_cols"][i], T["q18_y"] + T["row_step"] * (question - 18)
    raise ValueError(f"question {question} is outside 1-25")


def form_bubble_center(form: str) -> tuple[float, float]:
    return T["form_bubbles"][FORM_LETTERS.index(form)]


def id_bubble_center(column: int, digit: int) -> tuple[float, float]:
    x0, dx, y0, dy = T["id_bubble"]
    return x0 + dx * column, y0 + dy * digit


def keys_from_mapping(rows: list[dict[str, str]]) -> dict[str, dict[int, str]]:
    """{form: {printed question: key letter}} taken directly from the Mapping CSV rows."""
    keys: dict[str, dict[int, str]] = {f: {} for f in FORM_LETTERS}
    for r in rows:
        keys[r["Form"]][int(r["Question"])] = r["Key"]
    return keys


def check_key_sheets(keys: dict[str, dict[int, str]]) -> list[str]:
    """Spec section 6: three pages A, B, C, each with exactly one filled bubble per question 1-25."""
    p = []
    if list(keys) != list(FORM_LETTERS):
        p.append(f"Scantron key sheets: pages must be Forms {', '.join(FORM_LETTERS)} in order.")
    for form, k in keys.items():
        if sorted(k) != list(range(1, QUESTIONS_PER_EXAM + 1)):
            p.append(f"Scantron key sheet Form {form}: needs exactly one answer for each question 1-{QUESTIONS_PER_EXAM}.")
        bad = [q for q, letter in k.items() if letter not in CHOICE_LETTERS]
        if bad:
            p.append(f"Scantron key sheet Form {form}: questions {bad} don't have a single key letter A-E.")
    return p


# ---------------------------------------------------------------------------------------------------- drawing
def _y(y: float) -> float:
    return PAGE_H - y


def _square(c, center, size):
    x, y = center
    c.rect(x - size / 2, _y(y) - size / 2, size, size, stroke=0, fill=1)


def _empty_bubble(c, center, label: str):
    x, y = center
    grey = colors.Color(T["empty_grey"], T["empty_grey"], T["empty_grey"])
    c.setStrokeColor(grey)
    c.setLineWidth(T["empty_line"])
    c.circle(x, _y(y), T["empty_r"], stroke=1, fill=0)
    c.setFillColor(grey)
    c.setFont("Helvetica", T["bubble_font"])
    c.drawCentredString(x, _y(y) - T["bubble_font"] * 0.35, label)


def _filled_bubble(c, center):
    x, y = center
    c.setFillColor(colors.black)
    c.circle(x, _y(y), T["filled_r"], stroke=0, fill=1)


def _box(c, x, y, w, h, line=0.75):
    c.setStrokeColor(colors.black)
    c.setLineWidth(line)
    c.rect(x, _y(y) - h, w, h, stroke=1, fill=0)


def _page(c, form: str, key: dict[int, str], quiz_name: str, quiz_class: str, generated: str):
    # Alignment marks: the scanner can't read the page without these.
    c.setFillColor(colors.black)
    for center in T["large_squares"]:
        _square(c, center, T["large_square"])
    for center in T["small_squares"]:
        _square(c, center, T["small_square"])

    # Name box with the key label (plain hyphens, like the scanner's own key pages).
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(T["name_label"][0], _y(T["name_label"][1]), "Name")
    _box(c, *T["name_box"])
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(T["name_text"][0], _y(T["name_text"][1]), f"KEY - {quiz_name} - Form {form}")

    # Answer bubbles: the key letter filled, every other letter an empty grey outline.
    for q in range(1, QUESTIONS_PER_EXAM + 1):
        ax, ay = bubble_center(q, "A")
        c.setFillColor(colors.black)
        c.setFont("Helvetica", T["qnum_font"])
        c.drawRightString(ax - T["qnum_gap"], _y(ay + T["qnum_baseline"]), str(q))
        for letter in CHOICE_LETTERS:
            if key[q] == letter:
                _filled_bubble(c, bubble_center(q, letter))
            else:
                _empty_bubble(c, bubble_center(q, letter), letter)

    # Exam Form: fill this page's form letter.
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawCentredString(T["form_label"][0], _y(T["form_label"][1]), "Exam Form")
    _box(c, *T["form_box"])
    for f in FORM_LETTERS:
        if f == form:
            _filled_bubble(c, form_bubble_center(f))
        else:
            _empty_bubble(c, form_bubble_center(f), f)

    # Student ID: drawn so the page looks like the student sheet, but left empty.
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawString(T["id_label"][0], _y(T["id_label"][1]), "Student ID")
    bx, by, bw, bh = T["id_box"]
    _box(c, bx, by, bw, bh)
    cell = bw / T["id_cols"]
    c.setLineWidth(0.5)
    c.line(bx, _y(by + T["id_write_row"]), bx + bw, _y(by + T["id_write_row"]))
    for col in range(1, T["id_cols"]):
        c.line(bx + cell * col, _y(by), bx + cell * col, _y(by + T["id_write_row"]))
    for col in range(T["id_cols"]):
        for digit in range(10):
            _empty_bubble(c, id_bubble_center(col, digit), str(digit))

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawString(T["footer"][0], _y(T["footer"][1]),
                 f"{quiz_name} ({quiz_class}) - answer key, Form {form}. From Exam Maker, generated {generated}.")


def render_key_sheets(keys: dict[str, dict[int, str]], quiz_name: str, quiz_class: str, generated: str,
                      path: Path) -> None:
    """Write the 3-page PDF (Forms A, B, C). `generated` is the yyyy-mm-dd generation date."""
    c = rl_canvas.Canvas(str(path), pagesize=T["page"])
    c.setTitle(f"{quiz_name} - Scantron Keys")
    for form in FORM_LETTERS:
        _page(c, form, keys[form], quiz_name.strip(), quiz_class.strip(), generated)
        c.showPage()
    c.save()
