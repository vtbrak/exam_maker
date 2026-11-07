"""Pick alternates and build Forms A/B/C (Form A is the master; B and C are reshuffles of it)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import CHOICE_LETTERS, FORM_LETTERS
from .bank import Alternate, Bank, QuestionSlot
from .richtext import Run


@dataclass
class Selection:
    """Which Alt is used for each Question #, and which are locked against Randomize All."""
    alts: dict[str, str] = field(default_factory=dict)
    locked: set[str] = field(default_factory=set)

    def randomize(self, bank: Bank, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        for slot in bank.slots:
            if slot.qnum in self.locked and self.alts.get(slot.qnum) in {a.alt for a in slot.alts}:
                continue
            self.alts[slot.qnum] = rng.choice(slot.alts).alt

    def reroll(self, bank: Bank, qnum: str, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        slot = bank.slot(qnum)
        others = [a.alt for a in slot.alts if a.alt != self.alts.get(qnum)]
        if others:
            self.alts[qnum] = rng.choice(others)

    def reconcile(self, bank: Bank, rng: random.Random | None = None) -> None:
        """After a reload: keep choices that still exist, randomize the rest."""
        valid = {s.qnum: {a.alt for a in s.alts} for s in bank.slots}
        self.alts = {q: a for q, a in self.alts.items() if a in valid.get(q, set())}
        self.locked &= set(self.alts)
        for slot in bank.slots:
            if slot.qnum not in self.alts:
                self.alts[slot.qnum] = (rng or random.Random()).choice(slot.alts).alt


@dataclass
class PrintedQuestion:
    number: int                     # printed number on this form (1-25)
    master_number: int              # Form A number of the same question
    slot: QuestionSlot
    alt: Alternate
    order: list[int]                # order[p] = index into alt.choices printed at letter p
    master_letters: list[str]       # 5 letters: Form A letter for each of this form's letters A-E

    @property
    def choices(self) -> list[list[Run]]:
        return [self.alt.choices[i] for i in self.order]

    @property
    def key(self) -> str:
        return CHOICE_LETTERS[self.order.index(0)]


@dataclass
class Block:
    """Questions that print together; a linked set's image prints once above the block."""
    questions: list[PrintedQuestion]
    linked_set: str | None
    image_slot: QuestionSlot | None      # slot whose image to show above the block (linked sets only)
    intro: list[Run] | None = None       # the set's Set Intro passage, printed once above the block
    shuffled: bool = False               # questions inside the set are shuffled on each form


@dataclass
class Form:
    letter: str
    blocks: list[Block]

    @property
    def questions(self) -> list[PrintedQuestion]:
        return [q for b in self.blocks for q in b.questions]


def _layout(bank: Bank, rng: random.Random) -> list[list[QuestionSlot]]:
    """Shuffle block order; inside a linked set marked Shuffle Within Set, shuffle the questions too."""
    blocks = []
    for group in bank.blocks:
        group = list(group)
        if group[0].linked_set and group[0].shuffle_set:
            rng.shuffle(group)
        blocks.append(group)
    rng.shuffle(blocks)
    return blocks


def _make_blocks(slot_blocks, make_q) -> list[Block]:
    out, n = [], 1
    for group in slot_blocks:
        qs = []
        for slot in group:
            qs.append(make_q(n, slot))
            n += 1
        linked = group[0].linked_set
        # A shuffled set's first question may not be its sheet-first one, so find the set's image/intro by value.
        head_image = next((s for s in group if s.image), None) if linked else None
        head_intro = next((s.set_intro for s in group if s.set_intro), None) if linked else None
        out.append(Block(qs, linked, head_image, head_intro, bool(linked and any(s.shuffle_set for s in group))))
    return out


def build_forms(bank: Bank, selection: Selection, rng: random.Random | None = None) -> list[Form]:
    rng = rng or random.Random()

    # Form A: master order, each question's choices shuffled onto letters A..k.
    master: dict[str, PrintedQuestion] = {}

    def make_a(n, slot):
        alt = slot.alt(selection.alts[slot.qnum])
        order = list(range(len(alt.choices)))
        rng.shuffle(order)
        q = PrintedQuestion(n, n, slot, alt, order, list(CHOICE_LETTERS))
        master[slot.qnum] = q
        return q

    forms = [Form(FORM_LETTERS[0], _make_blocks(_layout(bank, rng), make_a))]

    # Forms B, C: new question order; choices reshuffled among the same used letters.
    for letter in FORM_LETTERS[1:]:
        def make_b(n, slot):
            a = master[slot.qnum]
            k = len(a.order)
            perm = list(range(k))              # perm[p] = Form A position printed at position p
            rng.shuffle(perm)
            order = [a.order[p] for p in perm]
            letters = [CHOICE_LETTERS[p] for p in perm] + list(CHOICE_LETTERS[k:])
            return PrintedQuestion(n, a.number, slot, a.alt, order, letters)
        forms.append(Form(letter, _make_blocks(_layout(bank, rng), make_b)))
    return forms
