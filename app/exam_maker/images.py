"""Image loading and sizing shared by the PDF and Word renderers.

PNG/JPG embed as-is. PDF/SVG are rendered to a 300 dpi PNG (page 1) with PyMuPDF.
"""
from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image as PILImage

from .bank import MAX_IMAGE_PCT

RASTER_DPI = 300
DEFAULT_DPI = 96          # used when a PNG/JPG doesn't record its dpi
_CACHE = Path(tempfile.gettempdir()) / "exam_maker_images"


@dataclass(frozen=True)
class LoadedImage:
    source: Path
    embed_path: Path          # PNG/JPG file to embed
    width_pt: float           # natural size in points
    height_pt: float

    @property
    def aspect(self) -> float:
        return self.width_pt / self.height_pt


@lru_cache(maxsize=256)
def _load(path: Path, mtime: float) -> LoadedImage:
    ext = path.suffix.lower()
    if ext in (".pdf", ".svg"):
        import fitz  # PyMuPDF

        _CACHE.mkdir(exist_ok=True)
        digest = hashlib.sha1(f"{path}|{mtime}".encode()).hexdigest()[:16]
        out = _CACHE / f"{digest}.png"
        with fitz.open(path) as doc:
            page = doc[0]
            w, h = page.rect.width, page.rect.height
            if not out.exists():
                pix = page.get_pixmap(matrix=fitz.Matrix(RASTER_DPI / 72, RASTER_DPI / 72), alpha=False)
                pix.save(out)
        return LoadedImage(path, out, w, h)

    with PILImage.open(path) as im:
        px_w, px_h = im.size
        dpi = im.info.get("dpi", (DEFAULT_DPI, DEFAULT_DPI))
        try:
            dx, dy = float(dpi[0]) or DEFAULT_DPI, float(dpi[1]) or DEFAULT_DPI
        except (TypeError, ValueError, IndexError):
            dx = dy = DEFAULT_DPI
        needs_convert = im.mode not in ("RGB", "RGBA", "L", "LA", "P") or ext not in (".png", ".jpg", ".jpeg")
        embed = path
        if needs_convert:
            _CACHE.mkdir(exist_ok=True)
            embed = _CACHE / (hashlib.sha1(f"{path}|{mtime}".encode()).hexdigest()[:16] + ".png")
            if not embed.exists():
                im.convert("RGB").save(embed)
    return LoadedImage(path, embed, px_w / dx * 72, px_h / dy * 72)


def load_image(path: Path) -> LoadedImage:
    return _load(Path(path), Path(path).stat().st_mtime)


def fit_size(img: LoadedImage, pct: int | None, page_h: float, max_w: float) -> tuple[float, float]:
    """Printed (width, height) in points, proportions locked.

    Height is the Image Height % of the page if given, otherwise the image's natural height;
    either way it never exceeds 20% of the page height, and the width never exceeds max_w.
    """
    cap = page_h * MAX_IMAGE_PCT / 100
    h = page_h * pct / 100 if pct else img.height_pt
    h = min(h, cap)
    w = h * img.aspect
    if w > max_w:
        w = max_w
        h = w / img.aspect
    return w, h


def thumbnail(path: Path, size: int = 56) -> PILImage.Image:
    img = load_image(path)
    with PILImage.open(img.embed_path) as im:
        im = im.convert("RGBA")
        im.thumbnail((size * 2, size * 2))
        return im.copy()
