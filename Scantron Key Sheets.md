# Exam Maker — Scantron Key Sheets for the Exam Scanner's key check

From: the integration conversation (Exam Maker ↔ Exam Scanner ↔ ExamGradeTool)
Date: 2026-10-07
Status: **Spec only. Not built yet.** For the Exam Maker conversation to build.

---

## 1. What and why

When it generates an exam, the Exam Maker also writes **one PDF of answer-key bubble sheets**: one page each for Forms A, B and C. Each page is the Exam Scanner's answer sheet with the correct answers already filled in.

The user prints the PDF and scans each page in the Exam Scanner's **key-check mode**: Keys tab → "Check key with a scanned sheet". The scanner compares the sheet with the key it imported from the Mapping CSV and lists any differences, e.g. "Form B Q7: imported C, scanned D".

**Why the Exam Maker prints them, not only the scanner.** The scanner can already print keys (Keys tab → "Answer keys (PDF)"), but it prints them from the key it imported. Scanning those back only proves the scanner reads its own printing. A key printed by the Exam Maker comes straight from the forms it built, so the check catches:

- a Mapping CSV from a different generation run than the forms that were printed;
- a mapping file that was edited or damaged on the way to the phone;
- a key changed by hand in the scanner after import;
- the scanner misreading a filled bubble.

Nothing changes in the Exam Scanner or ExamGradeTool. The scanner keeps its own key printing.

## 2. Output file

- **File name:** `<QuizName> - Scantron Keys.pdf`, e.g. `202630 Exam 1 - Scantron Keys.pdf`, in the same output folder as the forms and CSVs.
- **3 pages, in order Form A, Form B, Form C.** One full sheet per page, US Letter portrait (612 × 792 pt).
- Written together with the other files, and only if all of section 6's checks pass.
- The existing `Form X Key.pdf` files (the exam printed with answers marked) stay as they are. They're for reading; this PDF is for scanning.

## 3. Page layout

The page must match the Exam Scanner's sheet **exactly**, because the scanner finds the black squares and then reads each bubble at a fixed position relative to them. The geometry below is copied from the scanner's `app/engine.js` (`TPL`) and `app/pdfgen.js` (`sheetPage`), as of 2026-10-07.

**Coordinates:** PDF points (72 per inch), origin at the **top-left** of the page, y increasing **downward**. ReportLab's origin is bottom-left, so draw at `y_reportlab = 792 − y`. Print at 100%; the scanner corrects for scaling, so "Fit to page" also works.

### 3.1 Alignment marks (required: the scanner can't read a page without them)

| Mark | Shape | Centres (x, y) |
|---|---|---|
| 6 large squares | Solid black, 11.1 × 11.1 pt | (155.55, 188.15), (456.45, 188.15), (155.55, 396.05), (456.45, 396.05), (155.55, 603.85), (456.45, 603.85) |
| 3 small squares | Solid black, 7.8 × 7.8 pt | (306.0, 213.4), (306.0, 402.0), (306.0, 606.1) |

**No code bar.** The scanner doesn't use it, and the scanner's own sheet leaves it out.

**Nothing else solid black and square** near the marks: no logos, filled boxes or other heavy shapes inside or near the rectangle x 140–472, y 108–640.

### 3.2 Answer bubbles (25 questions × A–E)

Choice columns, x for A, B, C, D, E:

- **Left block:** 197.7, 212.7, 227.7, 242.7, 257.7
- **Right block:** 290.7, 305.7, 320.7, 335.7, 350.7

| Questions | Block | y of question n |
|---|---|---|
| 1–8 | Left | 231.13 + 20 × (n − 1) |
| 9–17 | Left | 419.72 + 20 × (n − 9) |
| 18–25 | Right | 231.13 + 20 × (n − 18) |

- **Filled bubble** (the key letter): solid black circle, radius 5.6 pt.
- **Empty bubble:** grey outline circle (60% grey, 0.5 pt line), radius 6 pt, with its letter in 6 pt grey type centred in it. The outlines are for people; the scanner ignores them.
- **Question number:** 9 pt, right-aligned, ending at x = (the question's A bubble x) − 8.5, baseline at y + 3.2.

### 3.3 Exam Form bubbles

- Form A, B, C bubbles at (284.72, 588.31), (299.72, 588.31), (314.72, 588.31). Same bubble style as above.
- **Fill this page's form letter.** The scanner reads it to pick which key to compare against. If it isn't filled, the scanner falls back to the form chosen on screen, so fill it.
- Label "Exam Form": 8 pt, centred at x 299.7, baseline y 575. Box outline around the bubbles: x 275.7, y 578.3, 48 × 20 pt.

### 3.4 Student ID

Leave **every ID bubble empty**; key-check mode doesn't read the ID.

Still draw the empty ID grid, so the page looks like the student sheet:

- 7 columns × digits 0–9, bubble centre (341.22 + 15 × column, 427.31 + 18 × digit).
- "Student ID" label at (333.7, 395), 8 pt.
- Outline box x 333.7, y 398.3, 105 × 200 pt, with a 20 pt-tall write-in row at the top divided into 7 cells.

### 3.5 Name box and footer

- "Name" label, 10 pt, at (172.2, 179). Box outline: x 172.2, y 182.6, 144 × 23 pt.
- **In the box:** `KEY - <QuizName> - Form <X>`, 8.5 pt bold, at (176, 197.5). Example: `KEY - 202630 Exam 1 - Form B`. This is the same label the scanner's own keys use.
- **Footer**, 8 pt at (150, 640): `<QuizName> (<QuizClass>) - answer key, Form <X>. From Exam Maker, generated <yyyy-mm-dd>.`

Use plain hyphens, not en or em dashes. The scanner's PDFs avoid them, and that keeps the two keys looking the same.

## 4. What gets filled

For each form and each printed question 1–25, fill exactly **one** bubble: that form's **Key** letter from the Mapping CSV rows the same run writes.

- **Take the letters from the mapping rows, not from a separate calculation.** Then the printed key and the Mapping CSV can't disagree because of an Exam Maker bug, and any difference the scanner reports is a real problem downstream.
- **Questions with fewer than 5 choices:** fill the key letter. It is always within the letters actually used (A–k).
- **Two-answer keys and dropped questions:** the Exam Maker never writes them. They're set later in the scanner, so a scanner-side change like this will correctly show up as a difference.

## 5. Interface

- The Exam Scanner export section of the screen gets one checkbox, **"Scantron key sheets (for the scanner's key check)"**, on by default.
- No other options.

## 6. Checks before writing

Added to the existing checks in `Exam Maker Export.md` §6:

- 3 pages: Forms A, B, C, in that order.
- Every page has exactly 25 filled answer bubbles, one per question, and exactly one filled form bubble matching the page.
- **Round-trip test (build-time unit test, not run on every generate):** render the PDF to an image at 150 dpi with PyMuPDF. Then, at each bubble centre from §3, check the mean darkness within a 4 pt radius: about 100% for every filled bubble, under 10% for every empty one, and solid black at each square from §3.1.

## 7. Keeping the layout in step with the scanner

The sheet geometry now lives in two places: the scanner's `engine.js` `TPL` and this Exam Maker code. **If either changes, both must change.**

- Keep the numbers from §3 in **one named constant block** in the Exam Maker code, e.g. `scantron_sheet.py` or `SHEET_TEMPLATE`. Its comment should say they mirror `Exam scanner/app/engine.js` `TPL` and point here.
- The Exam Scanner's `App Description.md` §2 has a matching note pointing to this file.
- A quick end-to-end check after any change: print one key page and run it through the scanner's key check. "The scanned sheet matches the key" means the layouts agree.

## 8. Decisions

Decided 2026-10-07:

- The Exam Maker prints its own key sheets so the scanner's key check compares two independent sources.
- One PDF, three pages (A, B, C), named `<QuizName> - Scantron Keys.pdf`.
- Same layout as the Exam Scanner's own sheet (no code bar). Name box `KEY - <QuizName> - Form <X>`. Student ID left blank. Form bubble filled.
- Filled letters come from the Mapping CSV rows of the same run.
