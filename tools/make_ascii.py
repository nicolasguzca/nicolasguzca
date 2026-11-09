"""Convert the GitHub avatar into the ASCII art the card draws.

Run by hand when the avatar changes; the output is committed, so the daily
workflow never needs Pillow:

    pip install pillow
    python tools/make_ascii.py            # downloads the current avatar
    python tools/make_ascii.py photo.jpg  # or converts a local file

Writes four files to assets/: ascii-{dark,light}.txt hold the characters and
ascii-{dark,light}.tone hold one tone code per character, same shape:

    i  ink     -- skin, outline, glasses: the card's foreground
    a  accent  -- hair and beard, drawn in the accent colour
    .  blank   -- background

The avatar is a sticker: a black-and-white illustration with a white outline
on a near-black ground. The ground is found by flood-filling dark pixels in
from the border, which stops at the outline, so the beard (just as dark as the
ground) stays inside the figure.
"""

from __future__ import annotations

import io
import sys
import urllib.request
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
USER = "nicolasguzca"

COLS = 60
# A character cell is ADVANCE wide and LINE tall (see build_card.py), so one
# cell covers CELL_ASPECT times as much width as height.
CELL_ASPECT = 0.5

GROUND_MAX = 70          # luminance at or below this, reached from the border, is ground
DARK_MAX = 85            # inside the figure: hair and beard
INK_RAMP = " .,:;ox%#@"  # light-on-dark ramp, sparse to dense
BEARD_RAMP = "=+"        # texture for the dark mass, alternated by position
# Gamma per theme. Dark: >1 thins the bright skin so the features show through.
# Light: <1 lifts the pale greys of the face off the page.
DARK_GAMMA = 1.6
LIGHT_GAMMA = 0.5


def ramp(v: float, gamma: float) -> str:
    v = max(0.0, min(1.0, v)) ** gamma
    return INK_RAMP[min(int(v * len(INK_RAMP)), len(INK_RAMP) - 1)]


def load(argv: list[str]) -> Image.Image:
    if len(argv) > 1:
        return Image.open(argv[1])
    url = f"https://avatars.githubusercontent.com/{USER}?s=460"
    with urllib.request.urlopen(url, timeout=30) as r:
        return Image.open(io.BytesIO(r.read()))


def ground_mask(lum: Image.Image) -> list[list[bool]]:
    w, h = lum.size
    px = lum.load()
    seen = [[False] * w for _ in range(h)]
    q = deque()
    for x in range(w):
        q.extend([(x, 0), (x, h - 1)])
    for y in range(h):
        q.extend([(0, y), (w - 1, y)])
    while q:
        x, y = q.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[y][x] or px[x, y] > GROUND_MAX:
            continue
        seen[y][x] = True
        q.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
    return seen


def main() -> None:
    img = load(sys.argv).convert("L")
    w, h = img.size
    ground = ground_mask(img)
    px = img.load()

    xs = [x for y in range(h) for x in range(w) if not ground[y][x]]
    ys = [y for y in range(h) for x in range(w) if not ground[y][x]]
    pad = 6
    x0, x1 = max(min(xs) - pad, 0), min(max(xs) + pad, w - 1)
    y0, y1 = max(min(ys) - pad, 0), min(max(ys) + pad, h - 1)

    cw = (x1 - x0 + 1) / COLS
    ch = cw / CELL_ASPECT
    rows = round((y1 - y0 + 1) / ch)

    dark_rows, dark_tone, light_rows, light_tone = [], [], [], []
    for r in range(rows):
        d_chars, d_tones, l_chars, l_tones = [], [], [], []
        for c in range(COLS):
            bx0, by0 = int(x0 + c * cw), int(y0 + r * ch)
            bx1, by1 = int(x0 + (c + 1) * cw), int(y0 + (r + 1) * ch)
            total = fg = 0
            lum_sum = dark = 0
            for y in range(by0, min(by1, h)):
                for x in range(bx0, min(bx1, w)):
                    total += 1
                    if ground[y][x]:
                        continue
                    fg += 1
                    lum_sum += px[x, y]
                    dark += px[x, y] <= DARK_MAX
            if total == 0 or fg / total < 0.45:
                d_chars.append(" "), d_tones.append(".")
                l_chars.append(" "), l_tones.append(".")
                continue
            lum = lum_sum / fg
            if dark / fg > 0.6:
                # Hair and beard: a textured accent mass on both themes.
                ch_ = BEARD_RAMP[(r + c) % 2]
                d_chars.append(ch_), d_tones.append("a")
                l_chars.append(ch_), l_tones.append("a")
                continue
            # Light-on-dark: brighter pixel, denser glyph.
            d = ramp(lum / 255, DARK_GAMMA)
            d_chars.append(d), d_tones.append("i" if d != " " else ".")
            # Dark-on-light: darker pixel, denser glyph. The white outline and
            # highlights vanish into the page, as they would in print.
            l = ramp((255 - lum) / 255, LIGHT_GAMMA)
            l_chars.append(l), l_tones.append("i" if l != " " else ".")
        dark_rows.append("".join(d_chars)), dark_tone.append("".join(d_tones))
        light_rows.append("".join(l_chars)), light_tone.append("".join(l_tones))

    ASSETS.mkdir(exist_ok=True)
    for name, rows_, tones in (("dark", dark_rows, dark_tone), ("light", light_rows, light_tone)):
        (ASSETS / f"ascii-{name}.txt").write_text("\n".join(rows_) + "\n")
        (ASSETS / f"ascii-{name}.tone").write_text("\n".join(tones) + "\n")
    print(f"{COLS} x {rows} -> assets/ascii-{{dark,light}}.{{txt,tone}}")


if __name__ == "__main__":
    main()
