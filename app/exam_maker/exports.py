"""Mapping CSV (Exam Scanner import) and Form Key CSV, per 'Exam Maker Export.md'.

check_* functions return a list of problems; the files are only written when all lists are empty.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from . import CHOICE_LETTERS, FORM_LETTERS, QUESTIONS_PER_EXAM
from .builder import Form
from .richtext import to_tags

MAPPING_COLUMNS = ["QuizName", "QuizClass", "QuizCreated", "Form", "Question", "MasterQuestion", "Key",
                   "A_MasterLetter", "B_MasterLetter", "C_MasterLetter", "D_MasterLetter", "E_MasterLetter"]
FORM_KEY_COLUMNS = ["QuizName", "Question", "Question #", "Alt", "Linked Set", "Form B Question", "Form C Question",
                    "Answer", "A", "B", "C", "D", "E"]

QUIZ_CLASS_RE = re.compile(r"^[0-9]{6}$")
QUIZ_CREATED_RE = re.compile(r"^(1[0-2]|[1-9])/(3[01]|[12][0-9]|[1-9])/[0-9]{2}$")


def check_quiz_fields(quiz_name: str, quiz_class: str, quiz_created: str) -> list[str]:
    problems = []
    if not quiz_name.strip():
        problems.append("QuizName is empty (e.g. '202630 Exam 1').")
    if not QUIZ_CLASS_RE.match(quiz_class.strip()):
        problems.append(f"QuizClass must be exactly 6 digits, the semester code (found '{quiz_class}').")
    if not QUIZ_CREATED_RE.match(quiz_created.strip()):
        problems.append(f"QuizCreated must be a date written m/d/yy with no leading zeros, e.g. 9/15/26 (found '{quiz_created}').")
    return problems


def mapping_rows(forms: list[Form], quiz_name: str, quiz_class: str, quiz_created: str) -> list[dict[str, str]]:
    rows = []
    for form in forms:
        for q in form.questions:
            row = {"QuizName": quiz_name.strip(), "QuizClass": quiz_class.strip(), "QuizCreated": quiz_created.strip(),
                   "Form": form.letter, "Question": str(q.number), "MasterQuestion": str(q.master_number),
                   "Key": q.key}
            for letter, master in zip(CHOICE_LETTERS, q.master_letters):
                row[f"{letter}_MasterLetter"] = master
            rows.append(row)
    return rows


def check_mapping(rows: list[dict[str, str]]) -> list[str]:
    """The Exam Scanner's import rules (exam-mapping-import.schema.json x-crossRowRules)."""
    p: list[str] = []
    n = QUESTIONS_PER_EXAM
    if len(rows) != n * len(FORM_LETTERS):
        p.append(f"Mapping has {len(rows)} rows; expected {n * len(FORM_LETTERS)}.")
    if any(list(r) != MAPPING_COLUMNS for r in rows):
        p.append("Mapping columns are not exactly the required columns in order.")
    for f in ("QuizName", "QuizClass", "QuizCreated"):
        if len({r[f] for r in rows}) != 1:
            p.append(f"{f} differs between rows.")
    expected = {str(i) for i in range(1, n + 1)}
    master_key: dict[str, str] = {}
    for form in FORM_LETTERS:
        fr = [r for r in rows if r["Form"] == form]
        if sorted(r["Question"] for r in fr) != sorted(expected):
            p.append(f"Form {form} does not have Questions 1-{n} exactly once.")
        if sorted(r["MasterQuestion"] for r in fr) != sorted(expected):
            p.append(f"Form {form} MasterQuestion values are not 1-{n} each once.")
        for r in fr:
            letters = [r[f"{c}_MasterLetter"] for c in CHOICE_LETTERS]
            if sorted(letters) != list(CHOICE_LETTERS):
                p.append(f"Form {form} Q{r['Question']}: MasterLetters are not A-E each once.")
            if r["Key"] not in CHOICE_LETTERS:
                p.append(f"Form {form} Q{r['Question']}: Key '{r['Key']}' is not a single letter A-E.")
            if form == FORM_LETTERS[0]:
                if r["MasterQuestion"] != r["Question"] or letters != list(CHOICE_LETTERS):
                    p.append(f"Form A Q{r['Question']}: must map to itself.")
                master_key[r["Question"]] = r["Key"]
    for r in rows:
        if r["Form"] == FORM_LETTERS[0] or r["Key"] not in CHOICE_LETTERS:
            continue
        translated = "".join(sorted(r[f"{k}_MasterLetter"] for k in r["Key"]))
        if translated != master_key.get(r["MasterQuestion"]):
            p.append(f"Form {r['Form']} Q{r['Question']}: Key {r['Key']} translates to {translated}, "
                     f"but Form A Q{r['MasterQuestion']} key is {master_key.get(r['MasterQuestion'])}.")
    return p


def check_linked_sets(forms: list[Form]) -> list[str]:
    p = []
    for form in forms:
        seen: dict[str, list[str]] = {}
        order = [q.slot for q in form.questions]
        for i, slot in enumerate(order):
            if slot.linked_set:
                seen.setdefault(slot.linked_set, []).append(i)
        for name, idxs in seen.items():
            if idxs != list(range(idxs[0], idxs[0] + len(idxs))):
                p.append(f"Form {form.letter}: Linked Set {name} is not kept together.")
    def members(b):   # a shuffled set only has to contain the same questions; a fixed set keeps its order
        qnums = [q.slot.qnum for q in b.questions]
        return tuple(sorted(qnums)) if b.shuffled else tuple(qnums)

    ref = [members(b) for b in forms[0].blocks if b.linked_set]
    for form in forms[1:]:
        got = [members(b) for b in form.blocks if b.linked_set]
        if sorted(ref) != sorted(got):
            p.append(f"Form {form.letter}: Linked Set contents or order differ from Form A.")
    return p


def form_key_rows(forms: list[Form], quiz_name: str) -> list[dict[str, str]]:
    a, b, c = forms
    where_b = {q.master_number: q.number for q in b.questions}
    where_c = {q.master_number: q.number for q in c.questions}
    rows = []
    for q in a.questions:
        row = {"QuizName": quiz_name.strip(), "Question": str(q.number), "Question #": q.slot.qnum,
               "Alt": q.alt.alt, "Linked Set": q.slot.linked_set or "",
               "Form B Question": str(where_b[q.number]), "Form C Question": str(where_c[q.number]),
               "Answer": to_tags(q.alt.choices[0])}
        texts = [to_tags(ch) for ch in q.choices]
        for i, letter in enumerate(CHOICE_LETTERS):
            row[letter] = texts[i] if i < len(texts) else ""
        rows.append(row)
    return rows


def check_form_key(rows: list[dict[str, str]]) -> list[str]:
    if sorted(r["Question"] for r in rows) != sorted(str(i) for i in range(1, QUESTIONS_PER_EXAM + 1)):
        return [f"Form Key does not have Form A Questions 1-{QUESTIONS_PER_EXAM} exactly once."]
    return []


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
