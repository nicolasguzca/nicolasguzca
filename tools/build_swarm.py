"""Render the contribution calendar being devoured by a Tyranid swarm,
with a Space Marine in hot pursuit.

Reads cache/calendar.json (tools/fetch_stats.py) and writes swarm_dark.svg and
swarm_light.svg.

The board keeps GitHub's calendar layout: 53 weeks by 7 days, months along the
top, Mon/Wed/Fri down the side, and the Less/More legend. A gaunt leads a pack
of rippers along each row in turn, alternating direction. Every day it passes
turns to creep, and the header counts the contributions consumed. A Space
Marine in ultramarine blue follows behind, firing as it chases. Once the
last row is stripped, the board resets and the swarm comes round again.

Rules that keep the animation cheap and in sync:

- No script. Everything is SMIL with calcMode="discrete" or linear motion,
  and every looping animation shares one duration and begins at 0, so the
  whole board stays in lock-step forever.
- Sprites are pixel art: each colour is one <path> of unit squares on a
  U-pixel grid, so neighbouring pixels never show seams.
- The pixel art is original. It nods to Tyranids (purple carapace, bone,
  scything talons) and to the Ultramarines (blue power armour, gold trim)
  without copying any Games Workshop artwork or iconography.

    python tools/build_swarm.py
"""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALENDAR = ROOT / "cache" / "calendar.json"

FONT = "'JetBrains Mono','SF Mono',Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"

# --- Geometry (px) ----------------------------------------------------------
WIDTH = 980            # same as the card, so the two stack as one unit
PAD = 28
LABEL_W = 34           # Mon/Wed/Fri column
HEADER_H = 40
MONTH_H = 20
LEGEND_H = 34
WEEKS = 53
U = 2                  # one sprite pixel

# --- Timing (s) -------------------------------------------------------------
STEP = 0.05            # time to cross one day
INTRO = 1.2            # full calendar before the swarm arrives
OUTRO = 2.6            # stripped calendar and the final tally before reset
CHOMP = 0.26           # one walk/bite cycle
EAT_AHEAD = 10         # px: a day is consumed as the maw (not the body centre) reaches it

THEMES = {
    "dark": {
        "bg": "#0B071D",
        "border": "#221d38",
        "ink": "#e8e8e8",
        "muted": "#6f6a85",
        "levels": ["#17132b", "#26306b", "#34489f", "#4560d6", "#7A9AFF"],
        "creep": "#3a1650",
        "tally": "#D4FF3A",
    },
    "light": {
        "bg": "#FAF9FC",
        "border": "#E2DFEA",
        "ink": "#1B1630",
        "muted": "#8f8aa0",
        "levels": ["#ebe9f1", "#c3cdfb", "#94a8fb", "#6680f6", "#3149C6"],
        "creep": "#d9c3ea",
        "tally": "#3149C6",
    },
}

# Sprite colours are the creatures', shared by both themes. The dark outline
# keeps the bone readable on the light board.
PALETTE = {
    "K": "#140a1f",  # outline
    "P": "#8e44e0",  # carapace
    "D": "#5b1f9c",  # carapace shade
    "B": "#efe4c8",  # bone
    "S": "#bfae86",  # bone shade
    "R": "#ff3d5e",  # eyes, maw
    "U": "#2f63e0",  # power armour, ultramarine blue
    "N": "#1b3a8c",  # armour shade
    "Y": "#e9b93a",  # gold trim
    "G": "#69707e",  # bolter
    "F": "#fff3b0",  # muzzle flash core
    "O": "#ff9b30",  # muzzle flash, bolt round
}

# Gaunt, facing right: domed carapace, hooked scything talon, open maw.
# Two frames: the legs stride and the jaws snap shut.
_GAUNT_TOP = [
    "...............KKK......",
    "..............KBBBK.....",
    ".............KBK.KBK....",
    "............KBK...KBK...",
    "....KKK....KBK.....KBK..",
    "..KKPPPKK.KBK.......KK..",
    ".KPPDPPPPKBBK...........",
    "KPPPPPDPPPKKKKKKKKK.....",
    "KDPPPDPPPPPPPDPPPPPKK...",
    ".KKPPPPPPPPPPPPPPPRPPK..",
    "...KKSBBBBBBBSKPPPPPPPK.",
]
GAUNT_FRAMES = [
    _GAUNT_TOP + [
        ".....KSBBBBBSKKBKBKBKK..",
        ".....KSK..KSK..K....K...",
        "....KSK....KSK.KBKBKK...",
        "...KSK......KSK.KKKK....",
        "...KK........KK.........",
    ],
    _GAUNT_TOP + [
        ".....KSBBBBBSKKBBBBBKK..",
        "......KSK.KSK...KKKK....",
        "......KSKKSK............",
        ".....KSK.KSK............",
        ".....KK..KK.............",
    ],
]

# Ripper: the small fry that trails the gaunt.
RIPPER_FRAMES = [
    [
        "....KKKK....",
        "..KKPDPPKK..",
        ".KPPPPPDPPK.",
        "KPDPPPPPPRPK",
        ".KKBBBBBBKBK",
        "...K.K.K.KK.",
    ],
    [
        "....KKKK....",
        "..KKPDPPKK..",
        ".KPPPPPDPPK.",
        "KPDPPPPPPRPK",
        ".KKBBBBBBBKK",
        "..K.K.K..K..",
    ],
]

# Space Marine in ultramarine blue, chasing the swarm. Two frames: a stride,
# then feet together with the bolter firing (flash plus a round in flight).
MARINE_FRAMES = [
    [
        ".....KKKK.............",
        "....KUUUUK............",
        "....KUUURK............",
        "....KUUNNK............",
        "..KKKKUUKKKK..........",
        ".KUUUUKKUUUUK.........",
        "KUUYUUUKUUUUUK........",
        "KUUUUUUKUKKKKKKKKK....",
        ".KKKKKUUKGGGGGGGGK....",
        "...KNUUUKKKGKKKKK.....",
        "...KUUYUUKKGK.........",
        "...KNUUUUK.K..........",
        "...KUUKUUK............",
        "..KUUK.KUUK...........",
        "..KUUK..KUUK..........",
        ".KNNNK..KNNNK.........",
        ".KKKKK..KKKKK.........",
    ],
    [
        ".....KKKK.............",
        "....KUUUUK............",
        "....KUUURK............",
        "....KUUNNK............",
        "..KKKKUUKKKK..........",
        ".KUUUUKKUUUUK.........",
        "KUUYUUUKUUUUUK....O...",
        "KUUUUUUKUKKKKKKKKKFO.O",
        ".KKKKKUUKGGGGGGGGKFFO.",
        "...KNUUUKKKGKKKKK.O...",
        "...KUUYUUKKGK.........",
        "...KNUUUUK.K..........",
        "....KUUUUK............",
        "....KUKKUK............",
        "....KUKKUK............",
        "...KNNKKNNK...........",
        "...KKKKKKKK...........",
    ],
]
MARINE_DELAY = 1.0   # s behind the gaunt
MARINE_DY = -6

# (delay s, y offset px, scale) for each ripper behind the gaunt.
PACK = [(0.16, -6, 1), (0.24, 5, 1), (0.34, -2, 1), (0.44, 6, 1), (0.55, -5, 1), (0.66, 2, 1)]


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def kt(values: list[float], total: float) -> str:
    """Times in seconds -> a strictly increasing keyTimes list in [0, 1)."""
    out, last = [], -1.0
    for v in values:
        f = max(v / total, last + 1e-5)
        out.append(f)
        last = f
    return ";".join(f"{f:.5f}" for f in out)


def sprite(rows: list[str], flip: bool) -> str:
    """Pixel map -> one <path> per colour, centred on (0, 0)."""
    if flip:
        rows = [r[::-1] for r in rows]
    h, w = len(rows), max(len(r) for r in rows)
    ox, oy = -w * U / 2, -h * U / 2
    paths: dict[str, list[str]] = {}
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            ch = row[x]
            if ch == ".":
                x += 1
                continue
            run = 1
            while x + run < len(row) and row[x + run] == ch:
                run += 1
            paths.setdefault(ch, []).append(
                f"M{ox + x * U:g} {oy + y * U:g}h{run * U}v{U}h{-run * U}z"
            )
            x += run
    return "".join(f'<path fill="{PALETTE[c]}" d="{"".join(d)}"/>' for c, d in paths.items())


def creature(frames: list[list[str]], flip: bool, T_chomp: float) -> str:
    """Two frames toggling every half cycle."""
    a, b = (sprite(f, flip) for f in frames)
    anim = f'calcMode="discrete" dur="{T_chomp}s" repeatCount="indefinite"'
    return (
        f'<g>{a}<animate attributeName="opacity" values="1;0" keyTimes="0;0.5" {anim}/></g>'
        f'<g opacity="0">{b}<animate attributeName="opacity" values="0;1" keyTimes="0;0.5" {anim}/></g>'
    )


def render(theme: str, days: list[dict]) -> str:
    c = THEMES[theme]

    # Lay the days on the grid. Column = week index from the first Sunday.
    first = dt.date.fromisoformat(days[0]["date"])
    sunday0 = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    cells = []
    for d in days:
        date = dt.date.fromisoformat(d["date"])
        col = (date - sunday0).days // 7
        cells.append({**d, "col": col, "row": d["weekday"], "date_obj": date})
    weeks = max(x["col"] for x in cells) + 1

    grid_x = PAD + LABEL_W
    pitch = (WIDTH - PAD - grid_x) / WEEKS
    cell = round(pitch * 0.78, 2)
    radius = round(cell * 0.2, 2)
    grid_y = PAD + HEADER_H + MONTH_H
    grid_h = 7 * pitch
    height = round(grid_y + grid_h + LEGEND_H + PAD - 10)

    def cx(col: int) -> float:
        return grid_x + col * pitch + cell / 2

    def cy(row: int) -> float:
        return grid_y + row * pitch + cell / 2

    # --- The route: a serpentine across the seven rows -----------------------
    x_left = cx(0) - pitch * 1.1
    x_right = cx(weeks - 1) + pitch * 1.1
    x_enter, x_exit = -40.0, WIDTH + 40.0
    speed = pitch / STEP

    segs = []  # (row, x_from, x_to, s_start)
    s = 0.0
    x = x_enter
    path = [f"M{x_enter:g} {cy(0):.2f}"]
    for r in range(7):
        going_right = r % 2 == 0
        target = (x_exit if r == 6 else x_right) if going_right else x_left
        segs.append((r, x, target, s))
        s += abs(target - x)
        path.append(f"H{target:.2f}")
        x = target
        if r < 6:
            path.append(f"V{cy(r + 1):.2f}")
            s += pitch
    route_len = s
    run = route_len / speed
    T = round(INTRO + run + OUTRO + MARINE_DELAY, 3)

    def eat_time(row: int, col: int) -> float:
        _, x0, _, s0 = segs[row]
        return INTRO + (s0 + abs(cx(col) - x0) - EAT_AHEAD) / speed

    for x_ in cells:
        x_["t"] = eat_time(x_["row"], x_["col"])

    # --- Document ------------------------------------------------------------
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="Contribution graph being devoured by a Tyranid swarm, chased by a Space Marine">',
        "<style>",
        f"text{{font-family:{FONT}}}.m{{fill:{c['muted']}}}.i{{fill:{c['ink']}}}"
        f".t{{fill:{c['tally']};font-weight:700}}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="14" fill="{c["bg"]}" stroke="{c["border"]}"/>',
    ]
    loop = f'dur="{T}s" repeatCount="indefinite"'

    # Header: running tally on the left, the year's total on the right.
    total = sum(d["count"] for d in days)
    hy = PAD + 18
    out.append(f'<text x="{grid_x}" y="{hy}" font-size="13" class="m">BIOMASS CONSUMED</text>')
    tally_x = grid_x + 142
    events = sorted((x_["t"], x_["count"]) for x_ in cells if x_["count"] > 0)
    running, stamps = 0, [(0.0, 0)]
    for t, n in events:
        running += n
        stamps.append((t, running))
    for i, (t, v) in enumerate(stamps):
        nxt = stamps[i + 1][0] if i + 1 < len(stamps) else None
        if i == 0:
            vals, times, start = "1;0", [0, nxt], "1"
        elif nxt is None:
            vals, times, start = "0;1", [0, t], "0"
        else:
            vals, times, start = "0;1;0", [0, t, nxt], "0"
        out.append(
            f'<text x="{tally_x}" y="{hy}" font-size="15" class="t" opacity="{start}">{v:,}'
            f'<animate attributeName="opacity" values="{vals}" keyTimes="{kt(times, T)}" calcMode="discrete" {loop}/></text>'
        )
    world_t = INTRO + run
    out.append(
        f'<text x="{tally_x + 70}" y="{hy}" font-size="13" class="t" opacity="0">· WORLD CONSUMED'
        f'<animate attributeName="opacity" values="0;1" keyTimes="0;{kt([world_t], T)}" calcMode="discrete" {loop}/></text>'
    )
    out.append(
        f'<text x="{WIDTH - PAD}" y="{hy}" font-size="13" text-anchor="end" class="m">'
        f'<tspan class="i">{total:,}</tspan> contributions in the last year</text>'
    )

    # Month labels over the week that holds the 1st, as GitHub does.
    for x_ in cells:
        d = x_["date_obj"]
        if d.day == 1 and x_["col"] < weeks - 2:
            out.append(
                f'<text x="{grid_x + x_["col"] * pitch:.2f}" y="{grid_y - 7}" font-size="11" class="m">{d.strftime("%b")}</text>'
            )
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{PAD}" y="{cy(r) + 4:.2f}" font-size="11" class="m">{name}</text>')

    # Days.
    for x_ in cells:
        fill = c["levels"][x_["level"]]
        out.append(
            f'<rect x="{grid_x + x_["col"] * pitch:.2f}" y="{grid_y + x_["row"] * pitch:.2f}" width="{cell}" height="{cell}" '
            f'rx="{radius}" fill="{fill}"><animate attributeName="fill" values="{fill};{c["creep"]}" '
            f'keyTimes="0;{kt([x_["t"]], T)}" calcMode="discrete" {loop}/></rect>'
        )

    # Legend.
    ly = grid_y + grid_h + 12
    lx = WIDTH - PAD - 5 * (cell + 4) - 34
    out.append(f'<text x="{lx - 8}" y="{ly + cell - 2}" font-size="11" text-anchor="end" class="m">Less</text>')
    for i, col in enumerate(c["levels"]):
        out.append(f'<rect x="{lx + i * (cell + 4):.2f}" y="{ly}" width="{cell}" height="{cell}" rx="{radius}" fill="{col}"/>')
    out.append(f'<text x="{lx + 5 * (cell + 4) + 4:.2f}" y="{ly + cell - 2}" font-size="11" class="m">More</text>')
    out.append(f'<rect x="{grid_x}" y="{ly}" width="{cell}" height="{cell}" rx="{radius}" fill="{c["creep"]}"/>')
    out.append(f'<text x="{grid_x + cell + 8}" y="{ly + cell - 2}" font-size="11" class="m">consumed</text>')

    # The swarm: rippers first so the gaunt draws on top.
    route = "".join(path)
    a_frac, b_frac = INTRO / T, (INTRO + run) / T

    def mover(body_right: str, body_left: str, delay: float, dy: float) -> str:
        flips = [INTRO + delay + s0 / speed for (_, _, _, s0) in segs]
        right_vals = ";".join("1" if r % 2 == 0 else "0" for r in range(7))
        left_vals = ";".join("0" if r % 2 == 0 else "1" for r in range(7))
        times = kt([0] + flips[1:], T)
        a = a_frac + delay / T
        b = b_frac + delay / T
        return (
            f'<g transform="translate(0 {dy})"><g>'
            f'<animateMotion path="{route}" keyPoints="0;0;1;1" keyTimes="0;{a:.5f};{b:.5f};1" calcMode="linear" {loop}/>'
            f'<g>{body_right}<animate attributeName="opacity" values="{right_vals}" keyTimes="{times}" calcMode="discrete" {loop}/></g>'
            f'<g opacity="0">{body_left}<animate attributeName="opacity" values="{left_vals}" keyTimes="{times}" calcMode="discrete" {loop}/></g>'
            f"</g></g>"
        )

    for delay, dy, _ in reversed(PACK):
        out.append(mover(creature(RIPPER_FRAMES, False, CHOMP * 0.8), creature(RIPPER_FRAMES, True, CHOMP * 0.8), delay, dy))
    out.append(mover(creature(GAUNT_FRAMES, False, CHOMP), creature(GAUNT_FRAMES, True, CHOMP), 0.0, -3))
    out.append(mover(creature(MARINE_FRAMES, False, CHOMP * 1.3), creature(MARINE_FRAMES, True, CHOMP * 1.3), MARINE_DELAY, MARINE_DY))

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    days = json.loads(CALENDAR.read_text())
    for theme in THEMES:
        (ROOT / f"swarm_{theme}.svg").write_text(render(theme, days))
    print("swarm_dark.svg swarm_light.svg")


if __name__ == "__main__":
    main()
