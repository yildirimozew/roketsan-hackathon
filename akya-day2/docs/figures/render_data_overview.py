"""Render an overview figure of the Stage 2 data: base, zones, frames, tracks, behaviors, risk rubric."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle
import numpy as np
import pandas as pd

DATA = Path(sys.argv[1])
OUT = Path(sys.argv[2])

# ---- palette (dataviz reference instance, light mode) ----
SURFACE, PAGE = "#fcfcfb", "#f9f9f7"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
LEVEL_COLOR = {"LOW": "#0ca30c", "MEDIUM": "#fab219", "HIGH": "#ec835a", "CRITICAL": "#d03b3b"}
FRAME_COLOR = "#2a78d6"  # categorical slot 1: drone frames

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": AXIS, "axes.facecolor": SURFACE, "figure.facecolor": PAGE,
})

# ---- load ----
scene = json.loads((DATA / "zones.json").read_text())
meta = json.loads((DATA / "image_meta.json").read_text())
reports = json.loads((DATA / "field_reports.json").read_text())
tracks = pd.read_csv(DATA / "tracks.csv").sort_values(["track_id", "time"])

B = scene["base"]
K = np.cos(np.radians(B["lat"]))
M_PER_DEG = 111_320


def to_xy_km(lat, lon):
    return (np.asarray(lon) - B["lon"]) * M_PER_DEG * K / 1000, (np.asarray(lat) - B["lat"]) * M_PER_DEG / 1000


tracks["x"], tracks["y"] = to_xy_km(tracks.lat, tracks.lon)
tracks["d"] = np.hypot(tracks.x, tracks.y)


def zone_of(x, y):
    best = min(scene["zones"], key=lambda z: np.hypot(*(np.subtract(to_xy_km(*z["center"]), (x, y)))))
    return best["name"]


# ---- per-track behavior + rubric ----
def classify(g):
    x, y, d = g.x.values, g.y.values, g.d.values
    step = np.hypot(np.diff(x), np.diff(y)) * 1000  # m per 5 min
    path = step.sum()
    ang = np.unwrap(np.arctan2(y, x))
    sweep = np.degrees(np.abs(ang - ang[0]).max())
    if path < 300:
        return "parked"
    if d[0] < 1.3 and d[-1] - d[0] > 1.5:
        return "departing"
    if sweep > 270:
        return "circling"
    if path > 12_000 and d.max() - d.min() < 0.6:
        return "orbit"
    if d[0] - d[-1] > 1.5:
        return "approaching"
    return "wandering"


def rubric(g):
    x, y, d = g.x.values, g.y.values, g.d.values * 1000
    step = np.hypot(np.diff(x), np.diff(y)) * 1000
    pts = 0
    pts += 30 if d[-1] < 1000 else 20 if d[-1] < 2000 else 10 if d[-1] < 4000 else 0
    rate = (d[-13] - d[-1]) / 60  # closing m/min over last 60 min
    pts += 25 if rate > 50 else 15 if rate > 20 else 5 if rate > 5 else 0
    dx, dy = x[-1] - x[-3], y[-1] - y[-3]
    if np.hypot(dx, dy) * 1000 > 100:  # moving over last 10 min
        to_base = np.arctan2(-y[-1], -x[-1])
        diff = np.degrees(np.abs((np.arctan2(dy, dx) - to_base + np.pi) % (2 * np.pi) - np.pi))
        pts += 10 if diff < 30 else 0
    # stops >= 20 min (4+ still steps) within 6 km
    still = step < 30
    runs, c = [], 0
    for i, s in enumerate(still):
        c = c + 1 if s else 0
        if c == 4:
            runs.append(i)
    near = [i for i in runs if d[i] < 6000]
    if near:
        pts += 10 + (5 if len(near) > 1 else 0)
    level = "CRITICAL" if pts >= 75 else "HIGH" if pts >= 50 else "MEDIUM" if pts >= 25 else "LOW"
    return pts, level, rate


rows = []
for tid, g in tracks.groupby("track_id"):
    pts, level, rate = rubric(g)
    rows.append(dict(track_id=tid, cls=classify(g), score=pts, level=level, rate=rate,
                     end=g.time.iloc[-1], d_end=g.d.iloc[-1], d_min=g.d.min()))
summary = pd.DataFrame(rows).set_index("track_id")
print(summary.groupby(["cls", "level"]).size().unstack(fill_value=0))

CLASSES = {
    "approaching": ("Steady approach", "Starts 5–8 km out, closes on the base\nwith 20–40 min stops en route."),
    "circling": ("Loops around the base", "Sweeps > 270° around the base,\ndips to ~0.5 km, then leaves."),
    "orbit": ("Fixed-range orbit", "~20 km driven at an almost constant\n1.6–5 km radius: patrol / surveillance."),
    "wandering": ("Mixed / transit", "Moves and stops without a clear\ntrend toward or away from base."),
    "departing": ("Leaving the base", "Parked < 1.2 km from base for 70–95 min,\nthen drives out to 2.5–5.5 km."),
    "parked": ("Parked", "No movement for 2 h (< 100 m of\nGPS jitter). Often no track at all."),
}

# ---- figure ----
fig = plt.figure(figsize=(22, 17.5), dpi=150)
FW, FH = 22, 17.5
fig.text(0.035, 0.975, "SENTINEL · Stage 2 data at a glance", fontsize=24, weight="bold")
fig.text(0.035, 0.955,
         f"{len(meta)} drone frames (10:10–15:50) · {tracks.track_id.nunique()} vehicle tracks "
         f"(2 h each, 5-min steps, each ends at a frame's capture time) · {len(reports)} field reports "
         f"({sum(r['source'] == 'official' for r in reports)} official, "
         f"{sum(r['source'] == 'third_party' for r in reports)} third-party, none flagged true/false)",
         fontsize=12.5, color=INK2)

EXT = 8.6


def base_map(ax, labels=True):
    ax.set_xlim(-EXT, EXT); ax.set_ylim(-EXT, EXT); ax.set_aspect("equal")
    ax.set_facecolor(SURFACE)
    for r, a in [(4, 0.05), (2, 0.07), (1, 0.10)]:
        ax.add_patch(Circle((0, 0), r, facecolor=LEVEL_COLOR["CRITICAL"], alpha=a, edgecolor="none", zorder=0))
        ax.add_patch(Circle((0, 0), r, fill=False, edgecolor=LEVEL_COLOR["CRITICAL"], lw=0.8, ls=(0, (4, 3)),
                            alpha=0.6, zorder=1))
    ax.add_patch(Circle((0, 0), 3.2, fill=False, edgecolor=MUTED, lw=0.8, ls=(0, (1, 2)), zorder=1))
    for z in scene["zones"]:
        zx, zy = to_xy_km(*z["center"])
        ax.plot(zx, zy, marker="D", ms=6 if labels else 3.5, mfc=SURFACE, mec=INK, mew=1.2, zorder=6)
    ax.plot(0, 0, marker="*", ms=22 if labels else 11, mfc=INK, mec=SURFACE, mew=1.5, zorder=7)
    ax.tick_params(length=0, labelsize=9)
    for s in ax.spines.values():
        s.set_color(AXIS)


def draw_tracks(ax, ids, lw=0.9, alpha=0.75, ends=True, ms=4):
    order = sorted(ids, key=lambda t: LEVELS.index(summary.at[t, "level"]))
    for tid in order:
        g = tracks[tracks.track_id == tid]
        c = LEVEL_COLOR[summary.at[tid, "level"]]
        ax.plot(g.x, g.y, color=c, lw=lw, alpha=alpha, solid_capstyle="round", zorder=3)
        if ends:
            ax.plot(g.x.iloc[-1], g.y.iloc[-1], "o", ms=ms, mfc=c, mec=SURFACE, mew=0.8, zorder=4)


# -- main map --
MAP_H = 0.5
ax = fig.add_axes([0.075, 0.42, MAP_H * FH / FW, MAP_H])
base_map(ax)
draw_tracks(ax, summary.index, lw=0.55, alpha=0.4, ms=4.5)
for img_id, m in meta.items():
    c = m["corner_coordinates"]
    x0, y1 = to_xy_km(*c["top_left"]); x1, y0 = to_xy_km(*c["bottom_right"])
    pad = 0.09  # frames are ~150 m wide; draw a visible footprint centred on the true one
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ax.add_patch(Rectangle((cx - pad, cy - pad * 0.56), 2 * pad, 2 * pad * 0.56, facecolor=FRAME_COLOR,
                           edgecolor=SURFACE, lw=0.6, zorder=5))
ax.text(-0.35, -0.35, "MERKEZ ÜS (base)\n39.92184 N, 32.85306 E", ha="right", va="top", fontsize=11, weight="bold", zorder=8,
        bbox=dict(fc=SURFACE, ec="none", alpha=0.85, pad=1.5))
compass = {"Kuzey Yolu": "N", "Kuzeydogu Kavsagi": "NE", "Dogu Yolu": "E", "Guneydogu Yerlesimi": "SE",
           "Guney Kapisi Yaklasimi": "S", "Guneybati Yolu": "SW", "Bati Yerlesimi": "W", "Kuzeybati Yolu": "NW"}
for z in scene["zones"]:
    zx, zy = to_xy_km(*z["center"])
    ang = np.arctan2(zy, zx)
    lx, ly = zx + 0.55 * np.cos(ang), zy + 0.55 * np.sin(ang)
    ha = "left" if np.cos(ang) > 0.3 else "right" if np.cos(ang) < -0.3 else "center"
    va = "bottom" if np.sin(ang) > 0.3 else "top" if np.sin(ang) < -0.3 else "center"
    ax.text(lx, ly, f"{z['name']} ({compass[z['name']]})\n{z['center'][0]:.5f} N, {z['center'][1]:.5f} E",
            fontsize=9.5, ha=ha, va=va, zorder=8, bbox=dict(fc=SURFACE, ec=AXIS, lw=0.6, pad=2.5,
                                                            boxstyle="round,pad=0.35"))
for r, lab in [(1, "1 km"), (2, "2 km"), (4, "4 km")]:
    ax.text(r * np.cos(np.radians(-62)), r * np.sin(np.radians(-62)), lab, fontsize=8.5,
            color=LEVEL_COLOR["CRITICAL"], ha="center", va="center", zorder=8,
            bbox=dict(fc=SURFACE, ec="none", pad=0.5, alpha=0.9))
ax.text(3.2 * np.cos(np.radians(-80)), 3.2 * np.sin(np.radians(-80)) - 0.12, "zone ring 3.2 km", fontsize=8.5,
        color=INK2, ha="center", va="top", zorder=8, bbox=dict(fc=SURFACE, ec="none", pad=0.5, alpha=0.9))
# lat/lon ticks for the km grid
ticks = np.arange(-8, 8.1, 2)
ax.set_xticks(ticks); ax.set_yticks(ticks)
ax.set_xticklabels([f"{t:+.0f} km\n{B['lon'] + t * 1000 / (M_PER_DEG * K):.3f}°E" for t in ticks])
ax.set_yticklabels([f"{B['lat'] + t * 1000 / M_PER_DEG:.3f}°N  {t:+.0f} km" for t in ticks])
ax.grid(color=GRID, lw=0.6, zorder=0.5)
ax.set_title("Where everything is: base, 8 zones, 40 frames and every vehicle's last 2 h", loc="left",
             fontsize=14, weight="bold", pad=10)
handles = [Line2D([], [], marker="*", ls="", ms=14, mfc=INK, mec=SURFACE, label="Base (Merkez Üs)"),
           Line2D([], [], marker="D", ls="", ms=7, mfc=SURFACE, mec=INK, mew=1.2, label="Zone centre (8)"),
           Line2D([], [], marker="s", ls="", ms=8, mfc=FRAME_COLOR, mec=SURFACE, label="Drone frame (40, enlarged)"),
           Line2D([], [], color=MUTED, lw=1.2, label="Track path (2 h)"),
           Line2D([], [], marker="o", ls="", ms=6, mfc=MUTED, mec=SURFACE, label="Position at capture time")]
handles += [Line2D([], [], color=LEVEL_COLOR[l], lw=3,
                   label=f"{l.title()} risk ({(summary.level == l).sum()} tracks)") for l in LEVELS]
ax.legend(handles=handles, loc="upper left", fontsize=9.5, frameon=True, facecolor=SURFACE, edgecolor=AXIS,
          ncol=1, borderpad=0.8, labelspacing=0.6)

# -- rubric panel --
rx = fig.add_axes([0.525, 0.42, 0.215, 0.5])
rx.axis("off")
rx.set_xlim(0, 1); rx.set_ylim(0, 1)
rx.text(0, 1.0, "What counts as dangerous", fontsize=14, weight="bold", va="top")
rx.text(0, 0.965, "Per-vehicle score 0–100 (rubric from docs/AGENT_DESIGN.md). The agent trusts\n"
                  "its own detection + track over any field report.", fontsize=10, color=INK2, va="top")
rubric_rows = [
    ("Distance to base now", "<1 / <2 / <4 km", "30 / 20 / 10"),
    ("Closing speed, 60 min", ">50 / >20 / >5 m/min", "25 / 15 / 5"),
    ("Heading at base, moving", "< 30°, last 10 min", "10"),
    ("Stop ≥ 20 min within 6 km", "+5 if repeated", "10 (+5)"),
    ("Vehicle type (detector)", "truck / bus / van", "10 / 8 / 5"),
    ("Corroborated report", "threat-relevant", "10"),
    ("No matching track", "unknown history", "0 + flag"),
]
y = 0.88
rx.text(0.0, y, "Factor", fontsize=9, color=MUTED, weight="bold")
rx.text(0.52, y, "Threshold", fontsize=9, color=MUTED, weight="bold")
rx.text(1.0, y, "Points", fontsize=9, color=MUTED, weight="bold", ha="right")
for i, (f, th, p) in enumerate(rubric_rows):
    y -= 0.047
    rx.plot([0, 1], [y + 0.028, y + 0.028], color=GRID, lw=0.7)
    faded = i >= 4
    rx.text(0.0, y, f, fontsize=10, color=INK2 if faded else INK)
    rx.text(0.52, y, th, fontsize=9.5, color=INK2)
    rx.text(1.0, y, p, fontsize=10, weight="bold", ha="right", color=INK2 if faded else INK)
y -= 0.035
rx.text(0.0, y, "Grey rows need the frame's detections/reports, so they are not in the\n"
                "track-only colours on this page (max here = 80).", fontsize=8.5, color=MUTED, va="top")
y -= 0.085
for lvl, rng in zip(LEVELS, ["0–24", "25–49", "50–74", "75–100"]):
    rx.add_patch(Rectangle((0.0, y - 0.006), 0.035, 0.022, color=LEVEL_COLOR[lvl]))
    rx.text(0.05, y + 0.005, f"{lvl}", fontsize=10, weight="bold", va="center")
    rx.text(0.24, y + 0.005, rng, fontsize=10, va="center", color=INK2)
    rx.text(1.0, y + 0.005, f"{(summary.level == lvl).sum()} tracks", fontsize=10, va="center", ha="right",
            color=INK2)
    y -= 0.034
fx = fig.add_axes([0.77, 0.42, 0.215, 0.5])
fx.axis("off"); fx.set_xlim(0, 1); fx.set_ylim(0, 1)
rx = fx
y = 1.0
rx.text(0, y, "Red flags in this data", fontsize=14, weight="bold", va="top")
flags = [
    "Closing fast: the 60-min approach rate is the strongest signal\n(up to ~100 m/min here); nothing ends closer than 1.55 km.",
    "Loops around the base: 5 tracks sweep > 270° and pass within\n0.5–0.8 km (reconnaissance pattern).",
    "Stop-and-go approach: 20–40 min halts inside 6 km, then\nmoving on toward the base.",
    "Heavy vehicle (truck/bus) doing any of the above.",
    "Reports are untrusted: many are off-topic (weather, last\nnight's hearsay); some claim a vehicle is “friendly/planned”.\nSuch a claim never lowers a level without evidence.",
]
y -= 0.045
for f in flags:
    rx.text(0.0, y, "▲", fontsize=9, color=LEVEL_COLOR["CRITICAL"], va="top")
    rx.text(0.045, y, f, fontsize=10, va="top", linespacing=1.35)
    y -= 0.03 + 0.03 * f.count("\n") + 0.03
rx.text(0, y - 0.01, "Frame level = highest vehicle level. The LLM may shift it by at most\none step, and only "
                     "with a cited reason.", fontsize=9, color=INK2, va="top")

# -- behavior facets: mini map + distance over time --
t_axis = np.arange(-120, 1, 5)
for col, (cls, (title, desc)) in enumerate(CLASSES.items()):
    ids = summary.index[summary.cls == cls]
    L, W = 0.035 + col * 0.1595, 0.14
    mx = fig.add_axes([L, 0.155, W, W * FW / FH])
    base_map(mx, labels=False)
    draw_tracks(mx, ids, lw=1.0, alpha=0.8, ms=3)
    mx.set_xticks([]); mx.set_yticks([])
    counts = summary.loc[ids, "level"].value_counts()
    mx.set_title(f"{title} · {len(ids)}", loc="left", fontsize=12, weight="bold", pad=30)
    mx.text(0, 1.015, desc, transform=mx.transAxes, fontsize=8.8, color=INK2, va="bottom")

    dx = fig.add_axes([L, 0.035, W, 0.095])
    dx.set_facecolor(SURFACE)
    for r in (1, 2, 4):
        dx.axhline(r, color=LEVEL_COLOR["CRITICAL"], lw=0.7, ls=(0, (4, 3)), alpha=0.6)
    order = sorted(ids, key=lambda t: LEVELS.index(summary.at[t, "level"]))
    for tid in order:
        g = tracks[tracks.track_id == tid]
        dx.plot(t_axis, g.d.values, color=LEVEL_COLOR[summary.at[tid, "level"]], lw=1.0, alpha=0.75)
    dx.set_xlim(-120, 0); dx.set_ylim(0, 8.5)
    dx.set_xticks([-120, -90, -60, -30, 0]); dx.set_xticklabels(["-2 h", "-90", "-60", "-30", "capture"])
    dx.set_yticks([0, 1, 2, 4, 6, 8])
    dx.tick_params(length=0, labelsize=8.5)
    dx.grid(axis="x", color=GRID, lw=0.6)
    for s in ("top", "right"):
        dx.spines[s].set_visible(False)
    if col == 0:
        dx.set_ylabel("km to base", fontsize=9.5)
    mix = "  ".join(f"{l[0]}{l[1:].lower()} {counts.get(l, 0)}" for l in LEVELS if counts.get(l, 0))
    dx.text(0.98, 0.95, mix, transform=dx.transAxes, fontsize=8.3, ha="right", va="top", color=INK2,
            bbox=dict(fc=SURFACE, ec="none", pad=1, alpha=0.9))

fig.text(0.035, 0.375, "What each vehicle is doing: 6 behaviour types (map: same extent as above · "
                     "chart: distance to base over the 2 h before capture)",
         fontsize=14, weight="bold")
fig.savefig(OUT, facecolor=PAGE)
print("wrote", OUT)
