"""Exam Maker: builds printable Scantron exam forms from a question-bank Excel file."""
from pathlib import Path

SCHEMA_VERSION = "1.2"
APP_DIR = Path(__file__).resolve().parent.parent      # .../exam maker/app
ROOT_DIR = APP_DIR.parent                              # .../exam maker
OUTPUT_DIR = ROOT_DIR / "Output"
FORM_LETTERS = ("A", "B", "C")
CHOICE_LETTERS = ("A", "B", "C", "D", "E")
QUESTIONS_PER_EXAM = 25
