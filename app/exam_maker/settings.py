"""Remember the window's fields between runs (app/settings.json)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

from . import APP_DIR

PATH = APP_DIR / "settings.json"
DEFAULT_INSTRUCTIONS = ("Choose the single best answer for each question and mark it on your Scantron form "
                        "using a No. 2 pencil.")


@dataclass
class Settings:
    bank_path: str = ""
    title: str = ""
    instructions: str = DEFAULT_INSTRUCTIONS
    quiz_name: str = ""
    quiz_class: str = ""
    font_size: str = "11"
    margin_in: str = "0.75"
    scantron_keys: str = "1"          # "1" = write the Scantron key sheets PDF (default on)

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        names = {f.name for f in fields(cls)}
        return cls(**{k: str(v) for k, v in data.items() if k in names})

    def save(self) -> None:
        try:
            PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass
