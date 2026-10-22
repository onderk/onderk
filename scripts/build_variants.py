"""Build light-theme copies of the dark SVG designs and the gallery strips.

Açık tema kopyalarını ve galeri şeritlerini üretir.

Sources (dark, hand-made):  assets/<name>.svg  and  assets/<name>_m.svg (phone)
Outputs:                    assets/<name>_light.svg, assets/<name>_m_light.svg
Gallery:                    assets/gallery/strip.jpg (desktop), strip_m.jpg (phone)

Run after any design change:  python scripts/build_variants.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DESIGNS = ["banner", "mcu_hub", "work_map"]

# dark colour -> light colour (backgrounds, text, lines). Accent colours stay.
LIGHT = {
    "#0b1220": "#f6f8fa", "#0f2a2e": "#e6f4f1", "#0f172a": "#ffffff", "#111827": "#ffffff",
    "#1f3b47": "#d0d7de", "#1e3a44": "#dfe5ec",
    "#f1f5f9": "#1f2328", "#e2e8f0": "#1f2328", "#94a3b8": "#57606a", "#64748b": "#6e7781",
    "#5eead4": "#0f766e", "#a5b4fc": "#4f46e5", "#67e8f9": "#0e7490", "#22d3ee": "#0891b2",
    "#34d399": "#059669", "#2dd4bf": "#0d9488", "#c4b5fd": "#7c3aed", "#93c5fd": "#2563eb",
}
_PATTERN = re.compile("|".join(re.escape(k) for k in LIGHT), re.I)


def to_light(svg: str) -> str:
    return _PATTERN.sub(lambda m: LIGHT[m.group(0).lower()], svg)


def build_svgs() -> list[str]:
    made = []
    for name in DESIGNS:
        for suffix in ("", "_m"):
            src = ASSETS / f"{name}{suffix}.svg"
            if not src.exists():
                raise SystemExit(f"missing source / kaynak yok: {src.name}")
            dst = ASSETS / f"{name}{suffix}_light.svg"
            dst.write_text(to_light(src.read_text(encoding="utf-8")), encoding="utf-8")
            made.append(dst.name)
    return made


def build_gallery() -> list[str]:
    from PIL import Image  # only needed for the gallery

    folder = ASSETS / "gallery"
    names = ["board_iso.jpg", "board_detail.jpg", "board_top.jpg"]
    imgs = [Image.open(folder / n).convert("RGB") for n in names]
    w, h = imgs[0].size
    gap = 16
    bg = (13, 17, 23)

    wide = Image.new("RGB", (3 * w + 2 * gap, h), bg)          # desktop: side by side
    for i, im in enumerate(imgs):
        wide.paste(im, (i * (w + gap), 0))
    wide = wide.resize((wide.width // 2, wide.height // 2), Image.LANCZOS)
    wide.save(folder / "strip.jpg", "JPEG", quality=84, optimize=True, progressive=True)

    tall = Image.new("RGB", (w, 3 * h + 2 * gap), bg)           # phone: stacked
    for i, im in enumerate(imgs):
        tall.paste(im, (0, i * (h + gap)))
    tall = tall.resize((tall.width * 3 // 4, tall.height * 3 // 4), Image.LANCZOS)
    tall.save(folder / "strip_m.jpg", "JPEG", quality=82, optimize=True, progressive=True)
    return ["gallery/strip.jpg", "gallery/strip_m.jpg"]


if __name__ == "__main__":
    print("ok:", ", ".join(build_svgs() + build_gallery()))
