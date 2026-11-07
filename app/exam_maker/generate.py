"""Generate every output file for one exam into Output/<QuizName> <yyyy-mm-dd>/."""
from __future__ import annotations

import datetime as dt
import random
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import OUTPUT_DIR
from .bank import Bank, version_from_filename
from .builder import Selection, build_forms
from .docx_render import render_docx
from .exports import (FORM_KEY_COLUMNS, MAPPING_COLUMNS, check_form_key, check_linked_sets, check_mapping,
                      check_quiz_fields, form_key_rows, mapping_rows, write_csv)
from .layout import ExamInfo
from .pdf_render import render_pdf
from .scantron_sheet import check_key_sheets, keys_from_mapping, render_key_sheets


KEYS_DIR = "Keys"          # answer-key PDFs
SCANNER_DIR = "Scanner"    # Mapping CSV (Exam Scanner import) + Form Key CSV


class GenerateError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass
class ExamRequest:
    bank: Bank
    selection: Selection
    info: ExamInfo
    quiz_name: str
    quiz_class: str
    quiz_created: str
    scantron_keys: bool = True      # also write '<QuizName> - Scantron Keys.pdf' for the scanner's key check


def safe_filename(s: str) -> str:
    s = re.sub(r'[/\\:*?"<>|]', "-", s.strip())
    return re.sub(r"\s+", " ", s).strip(" .") or "Exam"


def unique_folder(parent: Path, name: str) -> Path:
    path, n = parent / name, 2
    while path.exists():
        path = parent / f"{name} ({n})"
        n += 1
    return path


def check_request(req: ExamRequest) -> list[str]:
    problems = []
    if not req.info.title.strip():
        problems.append("Exam title is empty (e.g. 'BIO 110 – Exam 1').")
    version, problem = version_from_filename(req.bank.path)
    if problem:
        problems.append(problem)
    else:
        req.info.version = version
    problems += check_quiz_fields(req.quiz_name, req.quiz_class, req.quiz_created)
    missing = [s.qnum for s in req.bank.slots if s.qnum not in req.selection.alts]
    if missing:
        problems.append(f"No alternate chosen for Question # {', '.join(missing)}.")
    return problems


def generate(req: ExamRequest, output_root: Path = OUTPUT_DIR, rng: random.Random | None = None,
             today: dt.date | None = None) -> Path:
    problems = check_request(req)
    if problems:
        raise GenerateError(problems)

    forms = build_forms(req.bank, req.selection, rng)
    mrows = mapping_rows(forms, req.quiz_name, req.quiz_class, req.quiz_created)
    krows = form_key_rows(forms, req.quiz_name)
    problems = check_mapping(mrows) + check_linked_sets(forms) + check_form_key(krows)
    sheet_keys = keys_from_mapping(mrows)          # key sheets are filled from the same rows as the Mapping CSV
    if req.scantron_keys:
        problems += check_key_sheets(sheet_keys)
    if problems:
        raise GenerateError(["Internal check failed; no files were written:"] + problems)

    today = today or dt.date.today()
    name = safe_filename(req.quiz_name)
    stamp = today.isoformat()
    output_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".building-", dir=output_root))
    try:
        # Student forms at the top level; answer keys and scanner files in subfolders so they aren't printed by mistake.
        keys, scanner = work / KEYS_DIR, work / SCANNER_DIR
        keys.mkdir()
        scanner.mkdir()
        for form in forms:
            render_pdf(form, req.info, work / f"{name} - Form {form.letter}.pdf")
            render_docx(form, req.info, work / f"{name} - Form {form.letter}.docx")
            render_pdf(form, req.info, keys / f"{name} - Form {form.letter} Key.pdf", key=True, label="ANSWER KEY")
        if req.scantron_keys:
            render_key_sheets(sheet_keys, req.quiz_name, req.quiz_class, stamp, keys / f"{name} - Scantron Keys.pdf")
        write_csv(scanner / f"{name} - Mapping - {stamp}.csv", MAPPING_COLUMNS, mrows)
        write_csv(scanner / f"{name} - Form Key - {stamp}.csv", FORM_KEY_COLUMNS, krows)
        final = unique_folder(output_root, f"{name} {stamp}")
        work.rename(final)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return final


def preview(bank: Bank, selection: Selection, info: ExamInfo) -> Path:
    """Draft of Form A in a temp file (the version is shown when the file name has one)."""
    info.version = version_from_filename(bank.path)[0] or ""
    forms = build_forms(bank, selection)
    out = Path(tempfile.gettempdir()) / "exam_maker_preview"
    out.mkdir(exist_ok=True)
    path = out / f"{safe_filename(info.title or 'Exam')} - Form A (draft).pdf"
    render_pdf(forms[0], info, path, label="DRAFT PREVIEW")
    return path
