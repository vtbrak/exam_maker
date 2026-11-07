# Question Bank Schema 1.1: new "Set Intro" column

From: the Exam Maker conversation
Date: 2026-09-25
Status: **Done in the Exam Maker.** Pass this to the other tools that read or write question banks.

---

## 1. What changed

The question bank has one new **optional** column, **Set Intro**. It holds a passage or scenario that prints **once above a Linked Set**, before the set's image, for example "In Cell Biology lab you decide to explore mitochondrial function…".

Before 1.1, the only place for a passage was the first question's text. It then printed below the figure and was tied to one alternate.

The schema version goes from **1.0 → 1.1**. **1.0 files are still valid.** The column is optional, and a bank without it loads exactly as before.

## 2. The column

| | |
|---|---|
| Header (exact) | `Set Intro` |
| Position in the template | Right after `Linked Set` (columns are matched by header name, so position doesn't matter to a reader) |
| Required? | No |
| Type | Text. It may contain line breaks and the same formatting as Question text (`**bold**`, `*italic*`, `__underline__`, `~sub~`, `^sup^`, or native Excel formatting) |
| JSON key | `"Set Intro"`. Leave it out when blank, like every other blank cell |

## 3. Rules

1. **Needs a Linked Set.** A row with `Set Intro` must also have a `Linked Set` value. To give a single question a passage, make it a **set of one question**; that is now allowed and intended.
2. **First question of the set only** (rule ID `SET_INTRO_ON_FIRST`). Enter it on the set's first Question #, meaning first in sheet order. It can go on any one row of that Question #. If more than one row has it, the text must be identical. Other Question #s in the set must not have a Set Intro.
3. **Printing order for a set:** Set Intro → set image → the set's questions, in sheet order. When a set has an image but **no** Set Intro, the Exam Maker prints its default line instead: "Use the figure below to answer questions X–Y." For a one-question set it prints "…answer question X."
4. The Set Intro is **not** part of any alternate. Every alternate of the set's questions shares it.

The JSON Schema enforces "needs a Linked Set" (`dependentRequired`). Rules 2–4 are cross-row rules, listed in `x-crossRowRules`.

## 4. Files updated (all in the `exam maker` folder)

| File | Change |
|---|---|
| `exam_question_bank.schema.json` | `x-schemaVersion` 1.1, `x-changelog`, the `Set Intro` property, `dependentRequired`, the `SET_INTRO_ON_FIRST` cross-row rule. `schemaVersion` now accepts `"1.0"` or `"1.1"` |
| `Exam Question Template.xlsx` | New column. The sample set S1 (Q12–15) has an example Set Intro. The Column Guide describes it, and its schema version reads 1.1 |
| `Blank Question Bank.xlsx` | New column, empty |
| `211 Exam 2 Bank.xlsx` | Converted Exam 2. Its two passages are now Set Intros: S1 = Q9 (Figure 1, a set of one) and S2 = Q14–17 (Figure 2, ETC) |

## 5. What each tool needs to do

| Tool | Action |
|---|---|
| **Exam Maker** | Done. It reads, validates and prints Set Intro in both PDF and Word. |
| **Exam Scanner** | **Nothing.** It doesn't read question banks. The Mapping CSV format is unchanged (`exam-mapping-import.schema.json`). |
| **Exam Maker → Form Key CSV** (`Exam Maker Export.md` §5) | **No change.** The Set Intro is not a column in the Form Key CSV. The `Linked Set` column already identifies the set. |
| **Grade tool** | **Nothing.** |
| **Any tool that reads a question bank** | Accept the `Set Intro` column (1.0 readers that ignore unknown columns already do). If the tool shows or prints questions, show the Set Intro once above the set. |
| **Any tool that writes or edits a question bank** | Keep `Set Intro` on round-trip, never drop it. Write it only on the set's first Question #. Write `schemaVersion: "1.1"` in JSON, or leave "Schema version" on the Column Guide sheet as 1.1. |
| **Any validator** | Add rule 1 (Set Intro needs a Linked Set) and rule 2 (`SET_INTRO_ON_FIRST`). |

## 6. Example rows

| Question # | Alt | Linked Set | Set Intro | Question | Image |
|---|---|---|---|---|---|
| 14 | 1 | S2 | In Cell Biology lab you decide to explore mitochondrial function… Use the following figure to help you answer the next 4 questions | In your first experiment you add antimycin A… | exam2_fig2_etc.png |
| 15 | 1 | S2 | | In your second, totally separate experiment… | |
| 16 | 1 | S2 | | In your third… excess of AMP… | |
| 16 | 2 | S2 | | What effect would excess ATP… | |
| 17 | 1 | S2 | | In your fourth… | |

JSON for the first row:

```json
{ "Question #": 14, "Alt": 1, "Linked Set": "S2",
  "Set Intro": "In Cell Biology lab you decide to explore mitochondrial function… Use the following figure to help you answer the next 4 questions",
  "Question": "In your first experiment you add antimycin A…",
  "Answer": "Oxygen usage would decrease", "Distractor 1": "Oxygen usage would increase",
  "Distractor 2": "Oxygen usage would remain the same", "Image": "exam2_fig2_etc.png" }
```
