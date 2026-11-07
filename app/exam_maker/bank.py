"""Load and validate a question-bank Excel file (schema 1.2; older files without the newer optional columns still load).

Any problem raises BankError with every issue found, each naming the Excel row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from . import QUESTIONS_PER_EXAM
from .richtext import Run, cell_to_text, from_cell, plain

SHEET = "Questions"
REQUIRED = ["Question #", "Alt", "Question", "Answer", "Distractor 1"]
OPTIONAL = ["Linked Set", "Set Intro", "Shuffle Within Set", "Distractor 2", "Distractor 3", "Distractor 4", "Image", "Image Height %"]
DISTRACTORS = ["Distractor 1", "Distractor 2", "Distractor 3", "Distractor 4"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".pdf", ".svg"}
MAX_IMAGE_PCT = 20
YES, NO = {"yes", "y", "true"}, {"no", "n", "false"}


_SEMESTER_RE = re.compile(r"(?<!\d)\d{6}(?!\d)")


def version_from_filename(path: str | Path) -> tuple[str | None, str | None]:
    """(version, problem): the exam version is the one 6-digit semester code in the Excel file name."""
    name = Path(path).name
    codes = _SEMESTER_RE.findall(Path(path).stem)
    if len(codes) == 1:
        return codes[0], None
    if not codes:
        return None, (f"The file name '{name}' has no 6-digit semester code, which is printed as the exam's version. "
                      f"Rename it to include one, e.g. 'Exam 1 202530 Bank.xlsx'.")
    return None, f"The file name '{name}' has more than one 6-digit number ({', '.join(codes)}); keep only the semester code."


class BankError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass
class Alternate:
    qnum: str
    alt: str
    row: int
    question: list[Run]
    choices: list[list[Run]]          # index 0 is always the correct Answer

    @property
    def preview(self) -> str:
        return plain(self.question)


@dataclass
class QuestionSlot:
    qnum: str
    alts: list[Alternate] = field(default_factory=list)
    linked_set: str | None = None
    set_intro: list[Run] | None = None     # passage printed once above a linked set (first Question # only)
    shuffle_set: bool = False              # shuffle question order inside the linked set (first Question # only)
    image: Path | None = None
    image_pct: int | None = None

    def alt(self, label: str) -> Alternate:
        return next(a for a in self.alts if a.alt == label)


@dataclass
class Bank:
    path: Path
    slots: list[QuestionSlot]                 # sheet order (first appearance)
    blocks: list[list[QuestionSlot]]          # linked sets grouped; standalone = 1-item blocks

    @property
    def images_dir(self) -> Path:
        return self.path.parent / "images"

    def slot(self, qnum: str) -> QuestionSlot:
        return next(s for s in self.slots if s.qnum == qnum)


def _key(value) -> str:
    return cell_to_text(value).strip()


def load_bank(path: str | Path) -> Bank:
    path = Path(path)
    try:
        wb = load_workbook(path, rich_text=True)
    except Exception as e:  # noqa: BLE001 — any read failure is a user-facing message
        raise BankError([f"Couldn't open {path.name}: {e}"])
    if SHEET not in wb.sheetnames:
        raise BankError([f"No sheet named '{SHEET}'. Sheets found: {', '.join(wb.sheetnames)}."])
    ws = wb[SHEET]

    headers: dict[str, int] = {}
    problems: list[str] = []
    for cell in ws[1]:
        name = _key(cell.value)
        if not name:
            continue
        if name in headers:
            problems.append(f"Row 1: the header '{name}' appears twice.")
        headers[name] = cell.column - 1
    missing = [h for h in REQUIRED if h not in headers]
    if missing:
        raise BankError([f"Row 1: missing required column(s): {', '.join(missing)}."] + problems)

    def get(row, name):
        idx = headers.get(name)
        return None if idx is None or idx >= len(row) else row[idx]

    images_dir = path.parent / "images"
    slots: dict[str, QuestionSlot] = {}
    set_of: dict[str, set[str]] = {}
    image_rows: dict[str, list[tuple[int, str, int | None]]] = {}
    intro_rows: dict[str, list[tuple[int, list[Run]]]] = {}
    shuffle_rows: dict[str, list[tuple[int, bool]]] = {}

    for row in ws.iter_rows(min_row=2):
        r = row[0].row
        known = [get(row, h) for h in REQUIRED + OPTIONAL]
        if all(c is None or _key(c.value) == "" for c in known):
            continue  # blank row

        qnum = _key(get(row, "Question #").value)
        alt = _key(get(row, "Alt").value)
        row_ok = True
        for h in ("Question #", "Alt", "Question", "Answer", "Distractor 1"):
            if _key(get(row, h).value) == "":
                problems.append(f"Row {r}: '{h}' is empty.")
                row_ok = False

        filled = [get(row, d) is not None and _key(get(row, d).value) != "" for d in DISTRACTORS]
        for n in range(1, len(filled)):
            if filled[n] and not filled[n - 1]:
                problems.append(f"Row {r}: '{DISTRACTORS[n]}' is filled but '{DISTRACTORS[n - 1]}' is empty. Fill distractors left to right.")
                row_ok = False

        img_cell, pct_cell = get(row, "Image"), get(row, "Image Height %")
        img = _key(img_cell.value) if img_cell is not None else ""
        pct_raw = _key(pct_cell.value) if pct_cell is not None else ""
        pct: int | None = None
        if pct_raw:
            try:
                f = float(pct_raw.rstrip("%"))
                if not f.is_integer() or not 1 <= f <= MAX_IMAGE_PCT:
                    raise ValueError
                pct = int(f)
            except ValueError:
                problems.append(f"Row {r}: 'Image Height %' must be a whole number from 1 to {MAX_IMAGE_PCT} (found '{pct_raw}').")
            if not img:
                problems.append(f"Row {r}: 'Image Height %' is set but 'Image' is empty. Put both on the same row.")
        if img:
            if "/" in img or "\\" in img:
                problems.append(f"Row {r}: 'Image' should be just a filename (found '{img}').")
            elif Path(img).suffix.lower() not in IMAGE_EXTS:
                problems.append(f"Row {r}: image '{img}' must be PNG, JPG, PDF or SVG.")
            elif not (images_dir / img).is_file():
                problems.append(f"Row {r}: image '{img}' not found in the 'images' folder next to {path.name}.")

        if not qnum or not alt:
            continue
        slot = slots.setdefault(qnum, QuestionSlot(qnum))
        set_cell = get(row, "Linked Set")
        set_value = _key(set_cell.value) if set_cell is not None else ""
        set_of.setdefault(qnum, set()).add(set_value)
        intro_cell = get(row, "Set Intro")
        if intro_cell is not None and _key(intro_cell.value):
            if not set_value:
                problems.append(f"Row {r}: 'Set Intro' is filled but 'Linked Set' is empty. A Set Intro belongs to a Linked Set "
                                f"(a set can be a single question).")
            intro_rows.setdefault(qnum, []).append((r, from_cell(intro_cell)))
        shuffle_cell = get(row, "Shuffle Within Set")
        shuffle_raw = _key(shuffle_cell.value).lower() if shuffle_cell is not None else ""
        if shuffle_raw:
            if shuffle_raw not in YES | NO:
                problems.append(f"Row {r}: 'Shuffle Within Set' must be Yes, No or blank (found '{shuffle_cell.value}').")
            elif shuffle_raw in YES and not set_value:
                problems.append(f"Row {r}: 'Shuffle Within Set' is Yes but 'Linked Set' is empty.")
            else:
                shuffle_rows.setdefault(qnum, []).append((r, shuffle_raw in YES))
        if img:
            image_rows.setdefault(qnum, []).append((r, img, pct))
        if any(a.alt == alt for a in slot.alts):
            problems.append(f"Row {r}: Question # {qnum} already has an Alt '{alt}'. Each Alt must be unique within its Question #.")
            continue
        if not row_ok:
            continue
        choices = [from_cell(get(row, "Answer"))] + [from_cell(get(row, d)) for d, ok in zip(DISTRACTORS, filled) if ok]
        slot.alts.append(Alternate(qnum, alt, r, from_cell(get(row, "Question")), choices))

    # Cross-row rules
    if len(slots) != QUESTIONS_PER_EXAM:
        problems.append(f"Found {len(slots)} different Question # values; an exam needs exactly {QUESTIONS_PER_EXAM} "
                        f"(every question in a Linked Set counts).")
    for qnum, slot in slots.items():
        sets = set_of[qnum]
        if len(sets) > 1:
            problems.append(f"Question # {qnum}: its rows have different 'Linked Set' values ({', '.join(sorted(s or 'blank' for s in sets))}).")
        slot.linked_set = next(iter(sets)) or None if len(sets) == 1 else None
        rows = image_rows.get(qnum, [])
        if len({i for _, i, _ in rows}) > 1:
            problems.append(f"Question # {qnum}: rows {', '.join(str(r) for r, _, _ in rows)} name different images. "
                            f"An image belongs to the whole Question #; use one file.")
        elif rows:
            slot.image = images_dir / rows[0][1]
            pcts = {p for _, _, p in rows if p is not None}
            if len(pcts) > 1:
                problems.append(f"Question # {qnum}: different 'Image Height %' values on rows {', '.join(str(r) for r, _, _ in rows)}.")
            slot.image_pct = next(iter(pcts)) if pcts else None

        intros = intro_rows.get(qnum, [])
        if len({plain(t) for _, t in intros}) > 1:
            problems.append(f"Question # {qnum}: rows {', '.join(str(r) for r, _ in intros)} have different 'Set Intro' text. "
                            f"Enter it once, or make every copy identical.")
        elif intros:
            slot.set_intro = intros[0][1]
        shuffles = shuffle_rows.get(qnum, [])
        if len({v for _, v in shuffles}) > 1:
            problems.append(f"Question # {qnum}: rows {', '.join(str(r) for r, _ in shuffles)} disagree on 'Shuffle Within Set'.")
        slot.shuffle_set = any(v for _, v in shuffles)

    ordered = list(slots.values())
    blocks: list[list[QuestionSlot]] = []
    by_set: dict[str, list[QuestionSlot]] = {}
    for slot in ordered:
        if slot.linked_set:
            if slot.linked_set not in by_set:
                by_set[slot.linked_set] = []
                blocks.append(by_set[slot.linked_set])
            by_set[slot.linked_set].append(slot)
        else:
            blocks.append([slot])
    for name, members in by_set.items():
        for s in members[1:]:
            if s.shuffle_set:
                problems.append(f"Linked Set {name}: Question # {s.qnum} has 'Shuffle Within Set'. Put it only on the set's "
                                f"first Question # ({members[0].qnum}).")
            if s.set_intro:
                problems.append(f"Linked Set {name}: Question # {s.qnum} has a 'Set Intro'. A set's intro goes only on its "
                                f"first Question # ({members[0].qnum}).")
            if s.image:
                problems.append(f"Linked Set {name}: Question # {s.qnum} has an image. A set's image goes only on its "
                                f"first Question # ({members[0].qnum}).")

    if problems:
        raise BankError(problems)
    return Bank(path, ordered, blocks)
