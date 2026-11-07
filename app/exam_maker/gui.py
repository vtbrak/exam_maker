"""Exam Maker window: Setup / Questions / Page Settings tabs, Preview and Generate."""
from __future__ import annotations

import datetime as dt
import subprocess
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .bank import Bank, BankError, load_bank, version_from_filename
from .builder import Selection
from .generate import KEYS_DIR, SCANNER_DIR, ExamRequest, GenerateError, check_request, generate, preview
from .images import thumbnail
from .layout import ExamInfo
from .settings import DEFAULT_INSTRUCTIONS, Settings

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_IMPORTED = True
    _BASES = (ctk.CTk, TkinterDnD.DnDWrapper)
except Exception:  # noqa: BLE001 — drag and drop is optional
    _DND_IMPORTED = False
    _BASES = (ctk.CTk,)

SET_TINTS = [("#F9E1A8", "#6B5316"), ("#C7E3F6", "#1E4A63"), ("#D3EECB", "#2D5427"), ("#E6D5F3", "#4B2E63"),
             ("#F6D0C9", "#6A2F25")]
FONT_SIZES = ["10", "10.5", "11", "12", "13", "14"]
MARGINS = ["0.5", "0.6", "0.75", "0.9", "1.0"]
THUMB = 52


def today_mdyy(d: dt.date | None = None) -> str:
    d = d or dt.date.today()
    return f"{d.month}/{d.day}/{d:%y}"


def open_path(path: Path) -> None:
    subprocess.run(["open", str(path)], check=False)


def show_problems(parent, title: str, intro: str, problems: list[str]) -> None:
    """Modal popup listing every problem, scrollable."""
    win = ctk.CTkToplevel(parent)
    win.title(title)
    win.geometry("640x420")
    win.transient(parent)
    ctk.CTkLabel(win, text=intro, font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
                 justify="left", wraplength=600).pack(fill="x", padx=16, pady=(16, 8))
    box = ctk.CTkTextbox(win, wrap="word")
    box.pack(fill="both", expand=True, padx=16)
    box.insert("1.0", "\n".join(f"• {p}" for p in problems))
    box.configure(state="disabled")
    ctk.CTkButton(win, text="OK", width=100, command=win.destroy).pack(pady=12)
    win.after(100, lambda: (win.lift(), win.focus_force(), win.grab_set()))


class QuestionRow:
    def __init__(self, app: "App", parent, bank: Bank, qnum: str, tint):
        self.app, self.qnum = app, qnum
        slot = bank.slot(qnum)
        self.slot = slot
        self.frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=("gray95", "gray21"))
        self.frame.grid_columnconfigure(3, weight=1)

        bar = ctk.CTkFrame(self.frame, width=6, height=THUMB, corner_radius=3, fg_color=tint or "transparent")
        bar.grid(row=0, column=0, sticky="ns", padx=(6, 8), pady=6)

        label = f"Q {qnum}"
        if slot.linked_set:
            label += f"\nSet {slot.linked_set}"
        ctk.CTkLabel(self.frame, text=label, width=58, anchor="w", justify="left",
                     font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, sticky="w")

        self.thumb = ctk.CTkLabel(self.frame, text="", width=THUMB, height=THUMB)
        self.thumb.grid(row=0, column=2, padx=6, pady=6)
        if slot.image:
            try:
                im = thumbnail(slot.image, THUMB)
                self.thumb.configure(image=ctk.CTkImage(light_image=im, dark_image=im,
                                                        size=_fit(im.size, THUMB)))
            except Exception:  # noqa: BLE001 — a bad thumbnail shouldn't block the list
                self.thumb.configure(text="image")

        self.text = ctk.CTkLabel(self.frame, text="", anchor="w", justify="left", wraplength=470)
        self.text.grid(row=0, column=3, sticky="we", padx=6)

        ctrl = ctk.CTkFrame(self.frame, fg_color="transparent")
        ctrl.grid(row=0, column=4, padx=8)
        n = len(slot.alts)
        ctk.CTkLabel(ctrl, text=f"Alt ({n})", width=44).grid(row=0, column=0)
        self.alt_menu = ctk.CTkOptionMenu(ctrl, values=[a.alt for a in slot.alts], width=86,
                                          command=self._pick, dynamic_resizing=False)
        self.alt_menu.grid(row=0, column=1, padx=4)
        self.reroll_btn = ctk.CTkButton(ctrl, text="↻", width=32, command=self._reroll,
                                        state="normal" if n > 1 else "disabled")
        self.reroll_btn.grid(row=0, column=2, padx=4)
        self.lock_var = ctk.BooleanVar(value=qnum in app.selection.locked)
        ctk.CTkCheckBox(ctrl, text="Lock", width=60, variable=self.lock_var,
                        command=self._lock).grid(row=0, column=3, padx=(4, 0))
        self.refresh()

    def refresh(self):
        alt = self.slot.alt(self.app.selection.alts[self.qnum])
        self.alt_menu.set(alt.alt)
        text = alt.preview.replace("\n", " ")
        self.text.configure(text=text if len(text) <= 170 else text[:167] + "…")

    def _pick(self, value):
        self.app.selection.alts[self.qnum] = value
        self.refresh()

    def _reroll(self):
        self.app.selection.reroll(self.app.bank, self.qnum)
        self.refresh()

    def _lock(self):
        (self.app.selection.locked.add if self.lock_var.get() else self.app.selection.locked.discard)(self.qnum)


def _fit(size, box):
    w, h = size
    s = box / max(w, h)
    return max(1, int(w * s)), max(1, int(h * s))


class App(*_BASES):
    def __init__(self):
        super().__init__()
        self.dnd = False
        if _DND_IMPORTED:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd = True
            except Exception:  # noqa: BLE001
                self.dnd = False

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self.title("Exam Maker")
        self.geometry("1040x780")
        self.minsize(900, 640)

        self.settings = Settings.load()
        self.bank: Bank | None = None
        self.selection = Selection()
        self.rows: list[QuestionRow] = []
        self.busy = False

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(8, 0))
        self._build_setup(self.tabs.add("Setup"))
        self._build_questions(self.tabs.add("Questions"))
        self._build_page(self.tabs.add("Page Settings"))
        self._build_bottom()

        if self.dnd:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.settings.bank_path and Path(self.settings.bank_path).is_file():
            self.after(200, lambda: self.load(self.settings.bank_path, quiet_switch=True))
        self._update_buttons()

    # ---------- layout ----------
    def _field(self, parent, row, label, var, width=420, hint=""):
        ctk.CTkLabel(parent, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=(16, 12), pady=6)
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)
        e = ctk.CTkEntry(box, textvariable=var, width=width)
        e.pack(side="left")
        if hint:
            ctk.CTkLabel(box, text=hint, text_color=("gray40", "gray65"), anchor="w").pack(side="left", padx=10)
        return e

    def _section(self, parent, row, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=15, weight="bold"), anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(14, 2))

    def _build_setup(self, tab):
        tab.grid_columnconfigure(2, weight=1)
        self._section(tab, 0, "Question bank")
        fr = ctk.CTkFrame(tab, fg_color="transparent")
        fr.grid(row=1, column=0, columnspan=3, sticky="we", padx=16)
        fr.grid_columnconfigure(0, weight=1)
        self.bank_var = ctk.StringVar(value=self.settings.bank_path)
        ctk.CTkEntry(fr, textvariable=self.bank_var, state="readonly").grid(row=0, column=0, sticky="we", pady=6)
        ctk.CTkButton(fr, text="Browse…", width=100, command=self._browse).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(fr, text="Reload", width=90, command=self._reload).grid(row=0, column=2, padx=(8, 0))
        hint = "…or drag an Excel file anywhere onto this window." if self.dnd else \
            "(Drag and drop isn't available on this system; use Browse.)"
        self.bank_info = ctk.CTkLabel(tab, text=hint, text_color=("gray40", "gray65"), anchor="w")
        self.bank_info.grid(row=2, column=0, columnspan=3, sticky="w", padx=16)

        self._section(tab, 3, "Printed on the exam")
        self.title_var = ctk.StringVar(value=self.settings.title)
        self._field(tab, 4, "Exam title", self.title_var, hint="e.g. BIO 110 – Exam 1")
        ctk.CTkLabel(tab, text="Instructions", anchor="nw").grid(row=5, column=0, sticky="nw", padx=(16, 12), pady=6)
        self.instr = ctk.CTkTextbox(tab, width=560, height=90, wrap="word")
        self.instr.grid(row=5, column=1, columnspan=2, sticky="w", pady=6)
        self.instr.insert("1.0", self.settings.instructions)
        ctk.CTkButton(tab, text="Reset to default", width=130, fg_color="transparent", border_width=1,
                      text_color=("gray20", "gray85"),
                      command=lambda: (self.instr.delete("1.0", "end"), self.instr.insert("1.0", DEFAULT_INSTRUCTIONS))
                      ).grid(row=6, column=1, sticky="w")

        self._section(tab, 7, "Exam Scanner export")
        self.qname_var = ctk.StringVar(value=self.settings.quiz_name)
        self.qclass_var = ctk.StringVar(value=self.settings.quiz_class)
        self.qcreated_var = ctk.StringVar(value=today_mdyy())
        self._field(tab, 8, "QuizName", self.qname_var, hint="e.g. 202630 Exam 1  (also names the output folder)")
        self._field(tab, 9, "QuizClass", self.qclass_var, width=120, hint="6-digit semester code, e.g. 202630")
        self._field(tab, 10, "QuizCreated", self.qcreated_var, width=120, hint="m/d/yy, defaults to today")
        self.sheets_var = ctk.BooleanVar(value=self.settings.scantron_keys != "0")
        ctk.CTkCheckBox(tab, text="Scantron key sheets (for the scanner's key check)",
                        variable=self.sheets_var).grid(row=11, column=1, columnspan=2, sticky="w", pady=(6, 0))

    def _build_questions(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=6, pady=(4, 6))
        self.rand_btn = ctk.CTkButton(bar, text="Randomize All", width=140, command=self._randomize_all)
        self.rand_btn.pack(side="left")
        self.q_info = ctk.CTkLabel(bar, text="Load a question bank on the Setup tab.", anchor="w",
                                   text_color=("gray40", "gray65"))
        self.q_info.pack(side="left", padx=14)
        self.q_list = ctk.CTkScrollableFrame(tab)
        self.q_list.pack(fill="both", expand=True)
        self.q_list.grid_columnconfigure(0, weight=1)

    def _build_page(self, tab):
        self.font_var = ctk.StringVar(value=self.settings.font_size if self.settings.font_size in FONT_SIZES else "11")
        self.margin_var = ctk.StringVar(value=self.settings.margin_in if self.settings.margin_in in MARGINS else "0.75")
        self._section(tab, 0, "Page settings")
        ctk.CTkLabel(tab, text="Font size (pt)", anchor="w").grid(row=1, column=0, sticky="w", padx=(16, 12), pady=8)
        ctk.CTkOptionMenu(tab, values=FONT_SIZES, variable=self.font_var, width=100).grid(row=1, column=1, sticky="w")
        ctk.CTkLabel(tab, text="Margins (inches)", anchor="w").grid(row=2, column=0, sticky="w", padx=(16, 12), pady=8)
        ctk.CTkOptionMenu(tab, values=MARGINS, variable=self.margin_var, width=100).grid(row=2, column=1, sticky="w")
        ctk.CTkLabel(tab, justify="left", anchor="w", text_color=("gray40", "gray65"),
                     text="Paper: US Letter · Font: Georgia · Images: at most 20% of the page height, "
                          "proportions locked.\nUse Preview to check how these settings look before generating."
                     ).grid(row=3, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 0))

    def _build_bottom(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=12)
        self.status = ctk.CTkLabel(bar, text="", anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.gen_btn = ctk.CTkButton(bar, text="Generate Exams", width=160, height=36,
                                     font=ctk.CTkFont(size=14, weight="bold"), command=self._generate)
        self.gen_btn.pack(side="right")
        self.prev_btn = ctk.CTkButton(bar, text="Preview Form A", width=150, height=36, fg_color="transparent",
                                      border_width=2, text_color=("gray10", "gray90"), command=self._preview)
        self.prev_btn.pack(side="right", padx=10)

    # ---------- loading ----------
    def _browse(self):
        start = Path(self.bank_var.get()).parent if self.bank_var.get() else Path.home()
        path = filedialog.askopenfilename(parent=self, title="Choose a question bank",
                                          initialdir=str(start), filetypes=[("Excel workbook", "*.xlsx")])
        if path:
            self.load(path)

    def _reload(self):
        if self.bank_var.get():
            self.load(self.bank_var.get())

    def _on_drop(self, event):
        files = [f for f in self.tk.splitlist(event.data) if f.lower().endswith(".xlsx")]
        if files:
            self.load(files[0])
        else:
            messagebox.showwarning("Exam Maker", "Drop an Excel (.xlsx) question bank.", parent=self)

    def load(self, path: str, quiet_switch: bool = False):
        same_file = self.bank is not None and Path(path) == self.bank.path
        self.bank_var.set(path)
        self.settings.bank_path = path
        try:
            bank = load_bank(path)
        except BankError as e:
            self.bank = None
            self._clear_rows()
            self.q_info.configure(text="Fix the problems in the Excel file, then click Reload.")
            self.bank_info.configure(text=f"{Path(path).name}: {len(e.problems)} problem(s) found.")
            self._update_buttons()
            show_problems(self, "Question bank problems",
                          f"{Path(path).name} can't be used until these are fixed:", e.problems)
            return
        self.bank = bank
        if same_file:
            self.selection.reconcile(bank)
        else:
            self.selection = Selection()
            self.selection.randomize(bank)
        self._render_rows()
        versions = sum(len(s.alts) for s in bank.slots)
        sets = len([b for b in bank.blocks if b[0].linked_set])
        version, _ = version_from_filename(path)
        self.bank_info.configure(text=f"Loaded {Path(path).name}: {len(bank.slots)} questions, "
                                      f"{versions} versions, {sets} linked set(s). "
                                      + (f"Prints as Version {version}." if version else
                                         "No 6-digit semester code in the file name \u2014 rename it before generating."))
        self.q_info.configure(text=f"{len(bank.slots)} questions · pick an Alt, re-roll ↻, "
                                   f"or Lock to keep it during Randomize All.")
        self._set_status(f"Loaded {Path(path).name}.")
        self._update_buttons()
        if not quiet_switch:
            self.tabs.set("Questions")

    def _clear_rows(self):
        for r in self.rows:
            r.frame.destroy()
        self.rows = []

    def _render_rows(self):
        self._clear_rows()
        tints, n = {}, 0
        for slot in self.bank.slots:
            if slot.linked_set and slot.linked_set not in tints:
                tints[slot.linked_set] = SET_TINTS[n % len(SET_TINTS)]
                n += 1
        for i, slot in enumerate(self.bank.slots):
            row = QuestionRow(self, self.q_list, self.bank, slot.qnum, tints.get(slot.linked_set))
            row.frame.grid(row=i, column=0, sticky="we", pady=3, padx=2)
            self.rows.append(row)

    def _randomize_all(self):
        if not self.bank:
            return
        self.selection.randomize(self.bank)
        for r in self.rows:
            r.refresh()
        locked = len(self.selection.locked)
        self._set_status("Randomized all alternates" + (f" ({locked} locked kept)." if locked else "."))

    # ---------- actions ----------
    def _info(self) -> ExamInfo:
        return ExamInfo(title=self.title_var.get().strip(), instructions=self.instr.get("1.0", "end").strip(),
                        font_size=float(self.font_var.get()), margin_in=float(self.margin_var.get()))

    def _request(self) -> ExamRequest:
        return ExamRequest(self.bank, self.selection, self._info(), self.qname_var.get().strip(),
                           self.qclass_var.get().strip(), self.qcreated_var.get().strip(), self.sheets_var.get())

    def _run_bg(self, message: str, work, done):
        self.busy = True
        self._update_buttons()
        self._set_status(message)
        result = {}

        def target():
            try:
                result["value"] = work()
            except Exception as e:  # noqa: BLE001 — reported in the UI thread
                result["error"] = e
                result["trace"] = traceback.format_exc()

        t = threading.Thread(target=target, daemon=True)
        t.start()

        def poll():
            if t.is_alive():
                self.after(100, poll)
                return
            self.busy = False
            self._update_buttons()
            done(result)

        self.after(100, poll)

    def _preview(self):
        if not self.bank:
            return
        info = self._info()
        if not info.title:
            info.title = "(untitled exam)"

        def done(res):
            if "error" in res:
                self._set_status("Preview failed.")
                show_problems(self, "Preview failed", "The preview couldn't be made:", [str(res["error"])])
                return
            self._set_status("Preview opened.")
            open_path(res["value"])

        self._run_bg("Building preview…", lambda: preview(self.bank, self.selection, info), done)

    def _generate(self):
        if not self.bank:
            return
        req = self._request()
        problems = check_request(req)
        if problems:
            show_problems(self, "Can't generate yet", "Fix these on the Setup tab first:", problems)
            return
        self._save_settings()

        def done(res):
            if "error" in res:
                err = res["error"]
                self._set_status("Generation failed; no files were written.")
                probs = err.problems if isinstance(err, GenerateError) else [str(err)]
                show_problems(self, "Generation failed", "No files were written:", probs)
                return
            folder = res["value"]
            self._set_status(f"Saved to Output/{folder.name}")
            messagebox.showinfo("Exams created",
                                f"Saved to Output/{folder.name}\n\n"
                                f"• Forms A, B and C (PDF + Word)\n"
                                f"• {KEYS_DIR}/ — the 3 answer keys"
                                + (" + Scantron key sheets\n" if req.scantron_keys else "\n") +
                                f"• {SCANNER_DIR}/ — the Mapping CSV and Form Key CSV", parent=self)
            open_path(folder)

        self._run_bg("Generating exams…", lambda: generate(req), done)

    # ---------- misc ----------
    def _set_status(self, text):
        self.status.configure(text=text)

    def _update_buttons(self):
        state = "normal" if self.bank and not self.busy else "disabled"
        for b in (self.gen_btn, self.prev_btn, self.rand_btn):
            b.configure(state=state)

    def _save_settings(self):
        s = self.settings
        s.bank_path = self.bank_var.get()
        s.title = self.title_var.get()
        s.instructions = self.instr.get("1.0", "end").strip()
        s.quiz_name = self.qname_var.get()
        s.quiz_class = self.qclass_var.get()
        s.font_size = self.font_var.get()
        s.margin_in = self.margin_var.get()
        s.scantron_keys = "1" if self.sheets_var.get() else "0"
        s.save()

    def _on_close(self):
        self._save_settings()
        self.destroy()


def main():
    App().mainloop()
