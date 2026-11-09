"""Build the neofetch-style profile card: card_dark.svg and card_light.svg.

Inputs:
    assets/ascii-{dark,light}.txt / .tone   portrait (tools/make_ascii.py)
    assets/profile.json                      the text on the right
    cache/stats.json                         GitHub numbers (tools/fetch_stats.py)

Every text row is a fixed number of monospace columns rendered with
textLength, so the browser stretches or squeezes it to the exact pixel width.
GitHub serves the SVG as an image, which can't load web fonts; whichever
monospace font the viewer has, the dot leaders still line up.

    python tools/build_card.py
"""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
STATS = ROOT / "cache" / "stats.json"

FONT = "'JetBrains Mono','SF Mono',Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"
ADVANCE = 0.6  # em per glyph for the fonts above (Consolas is 0.55; textLength absorbs it)

# --- Geometry (px) ----------------------------------------------------------
WIDTH = 980
PAD = 28
ART_W = 360            # portrait column width
GUTTER = 34
PANEL_COLS = 60
PANEL_FONT = 14.5
PANEL_LINE = 24

THEMES = {
    "dark": {
        "bg": "#0B071D",
        "border": "#221d38",
        "ink": "#e8e8e8",
        "muted": "#6f6a85",
        "key": "#7A9AFF",
        "accent": "#5778FE",
        "user": "#D4FF3A",
    },
    "light": {
        "bg": "#FAF9FC",
        "border": "#E2DFEA",
        "ink": "#1B1630",
        "muted": "#9a95aa",
        "key": "#3149C6",
        "accent": "#5778FE",
        "user": "#3149C6",
    },
}


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def uptime(created: str, today: dt.date) -> str:
    start = dt.date.fromisoformat(created[:10])
    months = (today.year - start.year) * 12 + today.month - start.month
    if today.day < start.day:
        months -= 1
    y, m = divmod(months, 12)
    parts = [f"{y} year{'s' * (y != 1)}"]
    if m:
        parts.append(f"{m} month{'s' * (m != 1)}")
    return ", ".join(parts) + " on GitHub"


# --- Panel rows -------------------------------------------------------------
# A row is a list of (text, css-class) segments whose texts add up to exactly
# PANEL_COLS characters; row() asserts it, so a layout slip fails the build.

def leader(key: str, value: str, width: int) -> list[tuple[str, str]]:
    dots = width - len(key) - len(value) - 4
    if dots < 1:
        raise ValueError(f"{key}: {value!r} does not fit in {width} columns")
    return [(key, "k"), (": ", "m"), ("." * dots, "m"), (" ", "m"), (value, "v"), (" ", "m")]


def pair_row(fields: list[list[str]]) -> list[tuple[str, str]]:
    if len(fields) == 1:
        return leader(*fields[0], PANEL_COLS)
    sep = " | "
    left = PANEL_COLS // 2 - 1
    right = PANEL_COLS - left - len(sep)
    return leader(*fields[0], left) + [(sep, "m")] + leader(*fields[1], right)


def heading(title: str) -> list[tuple[str, str]]:
    head = f"- {title} "
    return [(head, "k"), ("-" * (PANEL_COLS - len(head)), "m")]


def blank() -> list[tuple[str, str]]:
    return [(" " * PANEL_COLS, "m")]


def panel_rows(profile: dict, stats: dict, today: dt.date) -> list[list[tuple[str, str]]]:
    who = f"{profile['user']}@{profile['host']}"
    rows = [[(profile["user"], "u"), ("@", "m"), (profile["host"], "v"), (" " + "-" * (PANEL_COLS - len(who) - 1), "m")]]
    fill = {"uptime": uptime(stats["created"], today)}
    for key, value in profile["about"]:
        rows.append(leader(key, value.format(**fill), PANEL_COLS))
    rows += [blank(), heading("Research")]
    rows += [pair_row(r) for r in profile["research"]]
    rows += [blank(), heading("Contact")]
    rows += [leader(k, v, PANEL_COLS) for k, v in profile["contact"]]
    rows += [blank(), heading("GitHub Stats")]
    rows.append(pair_row([["Repos", f"{stats['repos']:,}"], ["Contributed to", f"{stats['contributed_to']:,}"]]))
    rows.append(pair_row([["Stars", f"{stats['stars']:,}"], ["Followers", f"{stats['followers']:,}"]]))
    rows.append(pair_row([["Contribs (1y)", f"{stats['contributions_year']:,}"], ["All time", f"{stats['contributions_all_time']:,}"]]))
    for r in rows:
        n = sum(len(t) for t, _ in r)
        assert n == PANEL_COLS, f"row is {n} columns, expected {PANEL_COLS}: {r}"
    return rows


# --- Portrait ---------------------------------------------------------------

def art_runs(chars: str, tones: str) -> list[tuple[str, str]]:
    """Group a row into same-colour runs. Blanks join whatever run they sit in."""
    runs: list[list[str]] = []
    for ch, t in zip(chars, tones):
        if t == "." and runs:
            runs[-1][0] += ch
        elif runs and runs[-1][1] in (t, "."):
            runs[-1][0] += ch
            runs[-1][1] = t
        else:
            runs.append([ch, t])
    return [(text, tone if tone != "." else "i") for text, tone in runs]


def tspans(segments: list[tuple[str, str]]) -> str:
    return "".join(f'<tspan class="{c}">{esc(t)}</tspan>' for t, c in segments)


def render(theme: str, profile: dict, stats: dict, today: dt.date) -> str:
    c = THEMES[theme]
    art = (ASSETS / f"ascii-{theme}.txt").read_text().rstrip("\n").split("\n")
    tone = (ASSETS / f"ascii-{theme}.tone").read_text().rstrip("\n").split("\n")
    cols = max(len(r) for r in art)
    art = [r.ljust(cols) for r in art]
    tone = [t.ljust(cols, ".") for t in tone]

    art_adv = ART_W / cols
    art_font = art_adv / ADVANCE
    art_line = art_adv * 2          # matches make_ascii.CELL_ASPECT = 0.5
    art_h = art_line * len(art)

    rows = panel_rows(profile, stats, today)
    panel_w = WIDTH - PAD * 2 - ART_W - GUTTER
    panel_h = PANEL_LINE * len(rows)

    body_h = max(art_h, panel_h)
    footer_h = 26
    height = round(PAD * 2 + body_h + footer_h)

    art_y0 = PAD + (body_h - art_h) / 2
    panel_y0 = PAD + (body_h - panel_h) / 2
    panel_x = PAD + ART_W + GUTTER

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{esc(profile["user"])}@{esc(profile["host"])} profile card">',
        "<style>",
        f"text{{font-family:{FONT};white-space:pre}}",
        f".i{{fill:{c['ink']}}}.a{{fill:{c['accent']}}}.k{{fill:{c['key']}}}.m{{fill:{c['muted']}}}"
        f".v{{fill:{c['ink']}}}.u{{fill:{c['user']};font-weight:700}}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="14" fill="{c["bg"]}" stroke="{c["border"]}"/>',
    ]

    out.append(f'<g font-size="{art_font:.3f}" xml:space="preserve">')
    for i, (chars, tones) in enumerate(zip(art, tone)):
        if not chars.strip():
            continue
        y = art_y0 + art_line * (i + 0.78)
        out.append(
            f'<text x="{PAD}" y="{y:.2f}" textLength="{ART_W}" lengthAdjust="spacingAndGlyphs">'
            f"{tspans(art_runs(chars, tones))}</text>"
        )
    out.append("</g>")

    out.append(f'<g font-size="{PANEL_FONT}" xml:space="preserve">')
    for i, segs in enumerate(rows):
        if all(not t.strip() for t, _ in segs):
            continue
        y = panel_y0 + PANEL_LINE * (i + 0.75)
        out.append(
            f'<text x="{panel_x}" y="{y:.2f}" textLength="{panel_w}" lengthAdjust="spacingAndGlyphs">'
            f"{tspans(segs)}</text>"
        )
    out.append("</g>")

    note = f"refreshed daily by GitHub Actions · last run {stats['updated']}"
    out.append(
        f'<text x="{WIDTH - PAD}" y="{height - PAD + 4}" text-anchor="end" font-size="11" class="m">{esc(note)}</text>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    profile = json.loads((ASSETS / "profile.json").read_text())
    stats = json.loads(STATS.read_text())
    today = dt.date.fromisoformat(stats["updated"])
    for theme in THEMES:
        (ROOT / f"card_{theme}.svg").write_text(render(theme, profile, stats, today))
    print("card_dark.svg card_light.svg")


if __name__ == "__main__":
    main()
