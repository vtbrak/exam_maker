# Question Bank Schema 1.2: new "Shuffle Within Set" column

From: the Exam Maker conversation
Date: 2026-09-26
Status: **Done in the Exam Maker.** Pass this to the other tools that read or write question banks. It builds on 1.1 (`Schema 1.1 Change - Set Intro.md`).

---

## 1. What changed

The question bank has one new **optional** column, **Shuffle Within Set**. Until now a Linked Set always printed its questions in sheet order. With **Yes**, the set still stays together as one block with its Set Intro and image above it, but the **order of its questions is shuffled separately on each form**.

It was needed for Exam 3: Q1–8 all use one pathway figure but don't depend on each other's order. Sets whose questions refer to "the question above" leave it blank.

The schema version goes from **1.1 → 1.2**. **1.0 and 1.1 files are still valid.** A bank without the column behaves exactly as before, with every set in sheet order.

## 2. The column

| | |
|---|---|
| Header (exact) | `Shuffle Within Set` |
| Position in the template | Right after `Set Intro` (readers match by header name) |
| Required? | No |
| Values | `Yes` or `No`, or blank (= No). Case-insensitive. `Y`/`N` and `TRUE`/`FALSE` are also accepted. The template has a Yes/No dropdown |
| JSON key | `"Shuffle Within Set"`. Leave it out when blank |

## 3. Rules

1. **Needs a Linked Set.** `Yes` on a row with no `Linked Set` value is an error.
2. **First question of the set only** (rule ID `SHUFFLE_ON_FIRST`). Enter it on the set's first Question # (first in sheet order), on any one row of it. If several rows of that Question # have it, they must agree. Other Question #s in the set leave it blank.
3. **Printing:** the set is one block. Set Intro → set image → the set's questions, in **shuffled order** when Yes, or **sheet order** when blank or No.
4. **Every form shuffles on its own, Form A included.** A shuffled set's questions can be in a different order on A, B and C.

## 4. Effect on the exports (`Exam Maker Export.md`)

- **Mapping CSV: no format change.** Each row still maps a printed question to its Form A number (`MasterQuestion`), so the scanner handles a shuffled set like any other reordering. The import rules are unchanged, and the Exam Maker still checks them before writing.
- **Form Key CSV: no format change.**
- **Please update the wording** in `Exam Maker Export.md`, which that conversation owns. The Exam Maker already does the following:
  - §3 step 2 and step 4: "A Linked Set stays together as one block, in sheet order" → "…as one block, in sheet order **unless the set's Shuffle Within Set is Yes, in which case its questions are shuffled inside the block on each form**."
  - §6: "Linked Sets are together and in sheet order on every form" → "Linked Sets are together on every form, and in sheet order unless Shuffle Within Set is Yes."

## 5. What each tool needs to do

| Tool | Action |
|---|---|
| **Exam Maker** | Done. It reads and validates the column, shuffles inside the set per form, and checks the result. |
| **Exam Scanner** | **Nothing.** The mapping format is unchanged. |
| **Grade tool / Exam Records** | **Nothing.** |
| **Any tool that reads a question bank** | Accept the column. If the tool prints or orders questions, a Yes set may be shown in any order inside its block. |
| **Any tool that writes or edits a question bank** | Keep the column on round-trip and write it only on the set's first Question #. Write `schemaVersion: "1.2"` in JSON (the Column Guide sheet says 1.2). |
| **Any validator** | Add rule 1 and `SHUFFLE_ON_FIRST`, and accept Yes/No/Y/N/TRUE/FALSE or blank. |

## 6. Files updated (in the `exam maker` folder)

| File | Change |
|---|---|
| `exam_question_bank.schema.json` | `x-schemaVersion` 1.2, changelog, the `Shuffle Within Set` property, `SET_ORDER` reworded, new `SHUFFLE_ON_FIRST` rule. `schemaVersion` accepts 1.0, 1.1 or 1.2 |
| `Exam Question Template.xlsx`, `Blank Question Bank.xlsx` | New column with a Yes/No dropdown, Column Guide entry, version 1.2 |

## 7. Example

| Question # | Alt | Linked Set | Set Intro | Shuffle Within Set | Question | Image |
|---|---|---|---|---|---|---|
| 1 | 1 | S1 | | Yes | What could cause an increase in Ca⁺ in this smooth muscle cell? | exam3_smooth_muscle_pathway.png |
| 2 | 1 | S1 | | | What is the result on the import/export of calcium… | |
| … | | S1 | | | … (Q3–8) | |
| 15 | 1 | S3 | | | Acetylcholine binds to a GPCR on heart muscle… | exam3_gpcr_camp_pathway.png |
| 16 | 1 | S3 | | | Given the same pathway as the question above… | |
| 18 | 1 | S3 | | | In the trimeric G-protein (GPCR) pathway… | |

S3 has no Shuffle Within Set because Q16 refers to "the question above". Q17 sits between them in the sheet but isn't in the set. Set members don't have to be next to each other in the sheet.
