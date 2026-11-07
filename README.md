# Exam Maker

A Mac app that turns a question bank in Excel into printable multiple-choice Scantron exams. Each run makes three forms (A, B and C) with the same questions in a different random order. It also makes answer keys, and CSV files and key sheets for the Exam Scanner.

- 25 questions per exam, with up to 5 choices each
- Question order and choice order are shuffled on each form; Form A is the master
- Student forms come out as both PDF and Word. Answer keys are PDF only, with the correct choice in bold and highlighted
- Questions can include images (PNG, JPG, PDF or SVG). An image is never taller than 20% of the page, and its proportions are kept

## Requirements

- macOS
- [Anaconda](https://www.anaconda.com/download) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html), plus an internet connection the first time you run the app

You don't need to install any Python packages yourself. The app builds its own conda environment, called `exam_maker`, and doesn't change your other environments.

## Setup

1. Download this folder (`git clone https://github.com/vtbrak/exam_maker.git`, or **Code → Download ZIP** on GitHub).
2. Double-click **`Exam Maker.command`**.

The first launch takes a few minutes while the `exam_maker` environment is created. After that, the app opens straight away.

**If macOS won't open the file:**
- If it says the file is from an unidentified developer, right-click it, choose **Open**, then click **Open** again. You only need to do this once.
- If it says you don't have permission, which can happen with a ZIP download, run this once in Terminal from the folder:
  ```bash
  chmod +x *.command find_conda.sh
  ```

### Environment scripts

| File | What it does |
|---|---|
| `Exam Maker.command` | Starts the app. Creates or updates the environment first if needed. |
| `Setup Exam Maker Environment.command` | Creates or updates the environment on its own. Add `--rebuild` to delete it and build a clean copy. |
| `find_conda.sh` | Finds conda and reports whether the environment is ready, missing or out of date. Run it with `./find_conda.sh`. |
| `app/environment.yml`, `app/requirements.txt` | The package list. If you edit either file, the next launch updates the environment automatically. |

PyMuPDF is deliberately kept below version 2, because 2.x adds large extras the app doesn't use. To upgrade it, change the limit in `app/requirements.txt`, then run:
```bash
./"Setup Exam Maker Environment.command" --rebuild
```

## Making a question bank

Start from **`Blank Question Bank.xlsx`**. **`Exam Question Template.xlsx`** is a filled-in example. Write one bank per exam, on the **Questions** sheet:

| Column | Meaning |
|---|---|
| Question # | Position 1–25 on the exam. Several rows can share a number. |
| Alt | Labels the alternate versions of that question. One alternate is picked for each exam, and all three forms use the same pick. |
| Linked Set | Questions with the same set label stay together, in order. |
| Set Intro | Optional passage printed once above a linked set. Fill it in on the set's first question only. |
| Shuffle Within Set | `Yes` shuffles the questions inside the set on each form. Fill it in on the set's first question only. |
| Question | The question text. Bold, italic, superscript and subscript formatting in the cell is kept. |
| Answer | Always the **correct** choice. It is shuffled into a random position on each form. |
| Distractor 1–4 | The wrong choices. Leave unused ones blank. |
| Image | File name of an image in the `images` folder next to the bank. |
| Image Height % | Image height as a percentage of the page (maximum 20). |

The full column rules are in `exam_question_bank.schema.json`, which uses schema version 1.2. Columns the app doesn't recognise are ignored.

**The file name must include the 6-digit semester code**, for example `Exam 1 202630 Bank.xlsx`. It is printed on every page as "Version 202630", and the app won't generate exams without it.

A suggested layout keeps each exam in its own folder:
```
Exam 1 202630/
  Exam 1 202630 Bank.xlsx
  images/
    cell_diagram.png
```

## Using the app

**Setup tab**
- Choose the bank with **Browse…** or by dragging the Excel file onto the window. After you edit the Excel file, click **Reload**.
- Enter the **Exam title** printed at the top of each page (for example, "BIO 110 – Exam 1") and the instructions.
- Under **Exam Scanner export**, fill in:
  - **QuizName**, which also names the output folder
  - **QuizClass**, the 6-digit semester code
  - **QuizCreated**, which defaults to today
- The Scantron key sheets checkbox is on by default.

**Questions tab**
- Shows which alternate was picked for each question number.
- **↻** picks a different alternate at random, and the dropdown picks a specific one.
- **Lock** keeps a question's alternate when you click **Randomize All**.

**Page Settings tab**
- Sets the font size and margins. The paper is US Letter and the font is Georgia.

Click **Preview Form A** to check the layout in a draft PDF, then click **Generate Exams**. Any problems in the bank are listed in a pop-up, and nothing is written until you fix them.

The settings are remembered between runs.

## Output

Files go to `Output/<QuizName> <date>/`, and the folder opens in Finder when generation finishes:

```
Output/202630 Exam 1 2026-11-07/
  202630 Exam 1 - Form A.pdf  (+ .docx, and Forms B and C)   ← print these
  Keys/
    202630 Exam 1 - Form A Key.pdf  (and B, C)
    202630 Exam 1 - Scantron Keys.pdf     ← filled bubble sheets for the scanner's key check
  Scanner/
    202630 Exam 1 - Mapping - 2026-11-07.csv
    202630 Exam 1 - Form Key - 2026-11-07.csv   ← import these into the Exam Scanner
```

The answer keys are kept in `Keys/` so they don't get printed with the student forms by mistake. The CSV formats are described in `Exam Maker Export.md`, and the key sheets in `Scantron Key Sheets.md`.

## Privacy

This repository is public. `.gitignore` keeps the `Output/` folder, exam bank folders (`Exam */`) and personal settings out of Git, so real exams are never uploaded. Keep your banks in `Exam …` folders, or anywhere outside this folder.

## Running the tests

```bash
cd app && /opt/miniconda3/envs/exam_maker/bin/python tests/test_scantron_sheet.py
```
(Use the environment path that `./find_conda.sh` reports.)
