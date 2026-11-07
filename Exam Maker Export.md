# Exam Maker — Form Export

Status: **Built** (Mapping CSV, Form Key CSV and checks). Scantron Keys PDF: spec only (`Scantron Key Sheets.md`).
Last updated: 2026-10-07

---

## 1. Purpose

After the Exam Maker builds an exam from a question bank (`Exam Question Template.xlsx` / `exam_question_bank.schema.json`), it writes the files the other tools need:

```
Question bank ──► Exam Maker ──► Forms A, B, C (printed)
                             ├─► Mapping CSV   ──► Exam Scanner (answer keys for all 3 forms)
                             ├─► Scantron Keys PDF ──► Exam Scanner key check (see `Scantron Key Sheets.md`)
                             └─► Form Key CSV  (kept by the user: traces each question back to the bank)
```

The Exam Scanner's grade CSV then goes to the exam grade tool. The Exam Maker does not talk to the grade tool directly.

## 2. Typed in when generating

These are **not in the question bank**. The user types them into the Exam Maker each time an exam is generated.

| Field | Format | Example | Rule |
|---|---|---|---|
| QuizName | Text | `202630 Exam 1` | Not blank. By convention starts with the semester code. |
| QuizClass | Exactly 6 digits | `202630` | Semester code. Links the exam to the scanner roster with the same SemesterCode. |
| QuizCreated | Date, m/d/yy | `9/15/26` | Written without leading zeros. Default: today. |

## 3. Building the three forms

**Form A is the master.** Forms B and C are reshuffles of Form A.

1. **Pick one alternate per Question #.** The same alternate is used on **all three forms**. (The mapping assumes B and C contain exactly Form A's questions.)
2. **Form A order.** Shuffle the 25 Question #s into printed order 1–25. A Linked Set stays together as one block, in sheet order unless the set's Shuffle Within Set is Yes, in which case its questions are shuffled inside the block on each form (schema 1.2).
3. **Form A choices.** Put the Answer and Distractors on letters **A through k**, where k is the number of choices (2–5), in shuffled order. The Answer's letter is Form A's Key.
4. **Forms B and C.** Separately for each form:
   - Shuffle the question order again, with each Linked Set still kept together as one block, in sheet order unless the set's Shuffle Within Set is Yes, in which case its questions are shuffled inside the block on each form.
   - For each question, shuffle the choices **among the same letters A through k only**. A True/False question uses A–B on every form.
5. **Unused letters map to themselves.** For a question with k < 5 choices, letters after k are not printed and are written in the mapping as themselves (for a 2-choice question: `C_MasterLetter` = C, `D_MasterLetter` = D, `E_MasterLetter` = E).
6. **One correct answer.** The bank has one Answer per row, so every Key the Exam Maker writes is a single letter. Two-answer keys and dropped questions are set later in the Exam Scanner.

## 4. Mapping CSV (to the Exam Scanner)

Must match `Exam scanner/schemas/exam-mapping-import.schema.json` exactly. The scanner refuses the file otherwise.

- **File name:** `<QuizName> - Mapping - <yyyy-mm-dd>.csv`, e.g. `202630 Exam 1 - Mapping - 2026-09-24.csv`.
- **CSV, UTF-8, header row.** Columns in this order:
  `QuizName, QuizClass, QuizCreated, Form, Question, MasterQuestion, Key, A_MasterLetter, B_MasterLetter, C_MasterLetter, D_MasterLetter, E_MasterLetter`
- **No extra columns.** The scanner rejects any column not listed above.
- **75 rows:** Form A questions 1–25, then Form B 1–25, then Form C 1–25.

| Column | What to write |
|---|---|
| QuizName, QuizClass, QuizCreated | The typed values (section 2), the same on every row. QuizClass keeps all 6 digits. |
| Form | `A`, `B` or `C` |
| Question | Printed question number on this form, `1`–`25`, no leading zeros |
| MasterQuestion | The Form A question number this is. On Form A rows, equals Question. |
| Key | This form's letter for the correct answer |
| X_MasterLetter | For this form's choice X, the Form A letter of the same choice. Form A rows: `A B C D E`. |

**Worked example.** Form A question 12 has 3 choices: A = Mitochondrion (answer), B = Nucleus, C = Ribosome. On Form B it is printed as question 4 with B choices A = Ribosome, B = Mitochondrion, C = Nucleus. The Form B row is:

| Form | Question | MasterQuestion | Key | A_ | B_ | C_ | D_ | E_ |
|---|---|---|---|---|---|---|---|---|
| B | 4 | 12 | B | C | A | B | D | E |

## 5. Form Key CSV (trace back to the question bank)

The scanner's item analysis (DI, % correct, choice counts) is reported by **Form A question number**. This file links each Form A number to the bank row it came from. The scanner does not read it; the user keeps it with the exam.

- **File name:** `<QuizName> - Form Key - <yyyy-mm-dd>.csv`
- **CSV, UTF-8, header row, 25 rows** (one per Form A question, in order).

| Column | What to write |
|---|---|
| QuizName | Same as the mapping |
| Question | Form A question number, `1`–`25` |
| Question # | The bank's `Question #`, as text exactly as in the bank |
| Alt | The bank's `Alt` used on all three forms |
| Linked Set | The bank's `Linked Set`, blank if none |
| Form B Question | Where this question appears on Form B |
| Form C Question | Where this question appears on Form C |
| Answer | The correct answer's text, with formatting tags (for reading item analysis without opening the bank) |
| A … E | The Form A text of each choice; blank past the last choice |

With this file, an item analysis row "Question 12, choice C picked by 40%" can be read as "bank Question 7 / Alt 2, distractor *Ribosome*."

## 6. Checks before writing

The Exam Maker runs the scanner's import rules itself and refuses to write the files if any fail, so a bad file is never handed to the scanner:

- 75 mapping rows; each form has Questions 1–25 exactly once.
- For Forms B and C, MasterQuestion values are 1–25, each used once.
- Every row's five MasterLetter values are A–E, each used once.
- Translating each B/C Key through its MasterLetters gives the Form A Key for that MasterQuestion.
- QuizName, QuizClass (6 digits) and QuizCreated (m/d/yy) are filled in and the same on every row.
- Linked Sets are together on every form, and in sheet order unless Shuffle Within Set is Yes.
- The Form Key has 25 rows and every Form A Question appears once.

## 7. Decisions

Decided 2026-09-24:

- The same alternate is used for a Question # on all three forms.
- QuizName, QuizClass and QuizCreated are typed into the Exam Maker, not stored in the question bank.
- Questions with fewer than 5 choices shuffle only their used letters; unused letters map to themselves.
- The Exam Maker keeps the trace back to the bank (Form Key CSV); the scanner's mapping format is unchanged.
- StudentID is the only student ID across all tools; CustomID is not used.
- The `yyyy-mm-dd` in the Mapping CSV and Form Key CSV file names is the date the files were generated, not QuizCreated.
