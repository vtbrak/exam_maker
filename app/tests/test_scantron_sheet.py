"""Round-trip test for the Scantron key sheets ('Scantron Key Sheets.md' section 6).

Builds a real exam from the sample template, renders its key-sheet PDF at 150 dpi, and checks the darkness at
every position the Exam Scanner reads: filled bubbles ~100%, empty bubbles < 10%, alignment squares solid black.

Run from the app folder:  .venv/bin/python tests/test_scantron_sheet.py
"""
import random
import sys
import tempfile
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from exam_maker import CHOICE_LETTERS, FORM_LETTERS, ROOT_DIR  # noqa: E402
from exam_maker.bank import load_bank  # noqa: E402
from exam_maker.builder import Selection, build_forms  # noqa: E402
from exam_maker.exports import mapping_rows  # noqa: E402
from exam_maker.scantron_sheet import (SHEET_TEMPLATE as T, bubble_center, check_key_sheets,  # noqa: E402
                                       form_bubble_center, id_bubble_center, keys_from_mapping,
                                       render_key_sheets)

DPI = 150
SCALE = DPI / 72
RADIUS_PT = 4.0


def darkness(pix, center) -> float:
    """Mean darkness (0 = white, 1 = black) within RADIUS_PT of a top-left-origin point."""
    cx, cy = center[0] * SCALE, center[1] * SCALE
    r = RADIUS_PT * SCALE
    total = n = 0
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                total += 1 - pix.pixel(x, y)[0] / 255
                n += 1
    return total / n


def main() -> int:
    bank = load_bank(ROOT_DIR / "Exam Question Template.xlsx")
    sel = Selection()
    sel.randomize(bank, random.Random(11))
    forms = build_forms(bank, sel, random.Random(12))
    keys = keys_from_mapping(mapping_rows(forms, "202630 Exam 1", "202630", "10/7/26"))
    assert not check_key_sheets(keys), check_key_sheets(keys)

    failures, worst_filled, worst_empty = [], 1.0, 0.0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "keys.pdf"
        render_key_sheets(keys, "202630 Exam 1", "202630", "2026-10-07", path)
        doc = pymupdf.open(path)
        assert len(doc) == 3, f"expected 3 pages, got {len(doc)}"
        for page, form in zip(doc, FORM_LETTERS):
            assert (page.rect.width, page.rect.height) == T["page"], "page must be US Letter portrait"
            pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
            for center in T["large_squares"] + T["small_squares"]:
                if darkness(pix, (center[0], center[1])) < 0.95:
                    failures.append(f"Form {form}: alignment square at {center} is not solid black")
            filled = 0
            for q in range(1, 26):
                for letter in CHOICE_LETTERS:
                    d = darkness(pix, bubble_center(q, letter))
                    if letter == keys[form][q]:
                        filled += 1
                        worst_filled = min(worst_filled, d)
                        if d < 0.9:
                            failures.append(f"Form {form} Q{q}{letter}: key bubble only {d:.0%} dark")
                    else:
                        worst_empty = max(worst_empty, d)
                        if d >= 0.10:
                            failures.append(f"Form {form} Q{q}{letter}: empty bubble {d:.0%} dark")
            if filled != 25:
                failures.append(f"Form {form}: {filled} filled answer bubbles, expected 25")
            for f in FORM_LETTERS:
                d = darkness(pix, form_bubble_center(f))
                if (f == form) != (d >= 0.9) or (f != form and d >= 0.10):
                    failures.append(f"Form {form}: form bubble {f} is {d:.0%} dark")
            for col in range(T["id_cols"]):
                for digit in range(10):
                    d = darkness(pix, id_bubble_center(col, digit))
                    worst_empty = max(worst_empty, d)
                    if d >= 0.10:
                        failures.append(f"Form {form}: ID bubble col {col} digit {digit} is {d:.0%} dark")

    print(f"Key bubbles: darkest-required minimum {worst_filled:.0%}; empty bubbles: maximum {worst_empty:.0%}")
    if failures:
        print("FAILED:\n  " + "\n  ".join(failures[:30]))
        return 1
    print("PASSED: 3 pages, 25 key bubbles + 1 form bubble per page, empty bubbles and ID grid clear, squares solid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
