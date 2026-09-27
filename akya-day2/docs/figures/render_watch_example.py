"""Render a one-case storyboard of watch mode: 2 watchers x 4 sectors following T0122 (real data)."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle, Wedge
import numpy as np
import pandas as pd

DATA = Path(sys.argv[1])
OUT = Path(sys.argv[2])
TRACK = "T0122"

# ---- palette (dataviz reference instance, light mode) ----
SURFACE, PAGE = "#fcfcfb", "#f9f9f7"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
LEVEL_COLOR = {"LOW": "#0ca30c", "MEDIUM": "#fab219", "HIGH": "#d03b3b"}
WATCHER_COLOR = {"A": "#2a78d6", "B": "#1baf7a"}  # categorical slots 1 and 3
WATCHER_TINT = {"A": "#e3eefb", "B": "#dff3ea"}
TRACKER = "#4a3aa7"

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": AXIS, "axes.facecolor": SURFACE, "figure.facecolor": PAGE,
})

scene = json.loads((DATA / "zones.json").read_text())
B = scene["base"]
K = np.cos(np.radians(B["lat"]))


def xy(lat, lon):
    return (np.asarray(lon) - B["lon"]) * 111.32 * K, (np.asarray(lat) - B["lat"]) * 111.32


tr = pd.read_csv(DATA / "tracks.csv")
g = tr[tr.track_id == TRACK].sort_values("time").reset_index(drop=True)
g["x"], g["y"] = xy(g.lat, g.lon)
g["d"] = np.hypot(g.x, g.y)
g["min"] = [int(t[:2]) * 60 + int(t[3:]) for t in g.time]

# Illustrative watcher decisions per tick (see steps below)
def level_at(t):
    if t < "12:50":
        return "LOW"
    if t < "14:05":
        return "MEDIUM"
    return "HIGH"


g["level"] = [level_at(t) for t in g.time]

# Sectors: nearest-zone cells are 45-degree wedges centred on each zone's bearing.
PRETTY = {"Kuzey Yolu": "Kuzey Yolu", "Kuzeydogu Kavsagi": "Kuzeydoğu Kavşağı", "Dogu Yolu": "Doğu Yolu",
          "Guneydogu Yerlesimi": "Güneydoğu Yerleşimi", "Guney Kapisi Yaklasimi": "Güney Kapısı Yaklaşımı",
          "Guneybati Yolu": "Güneybatı Yolu", "Bati Yerlesimi": "Batı Yerleşimi", "Kuzeybati Yolu": "Kuzeybatı Yolu"}
OWNER = {"Bati Yerlesimi": "A", "Kuzeybati Yolu": "A", "Kuzey Yolu": "A", "Kuzeydogu Kavsagi": "A",
         "Dogu Yolu": "B", "Guneydogu Yerlesimi": "B", "Guney Kapisi Yaklasimi": "B", "Guneybati Yolu": "B"}

fig = plt.figure(figsize=(22, 14), dpi=150)
FW, FH = 22, 14
fig.text(0.03, 0.965, "Watch mode, one case: two watchers hand a dangerous truck to the supervisor",
         fontsize=23, weight="bold")
fig.text(0.03, 0.94, "Real track T0122 from tracks.csv (organizer example img_000860). 8 sectors, 2 watchers "
                     "with 4 sectors each. Levels are the watchers' illustrative decisions; the tracker part is simulated.",
         fontsize=12.5, color=INK2)

# ================= map =================
MAP_H = 0.62
ax = fig.add_axes([0.03, 0.29, MAP_H * FH / FW, MAP_H])
EXT = 6.9
ax.set_xlim(-EXT, EXT); ax.set_ylim(-EXT, EXT); ax.set_aspect("equal")
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_color(AXIS)

for z in scene["zones"]:
    zx, zy = xy(*z["center"])
    ang = np.degrees(np.arctan2(zy, zx))  # math angle
    w = OWNER[z["name"]]
    ax.add_patch(Wedge((0, 0), 10, ang - 22.5, ang + 22.5, facecolor=WATCHER_TINT[w], edgecolor=SURFACE,
                       lw=1.5, zorder=0))
    ax.plot(zx, zy, marker="D", ms=7, mfc=SURFACE, mec=INK2, mew=1.2, zorder=3)
    lx, ly = zx * 1.27, zy * 1.27
    ax.text(lx, ly, PRETTY[z["name"]], fontsize=9.5, color=INK2, ha="center", va="center", zorder=3)
# boundary between the two watchers (bearing 67.5 / 247.5 deg = math angle 22.5 / 202.5)
for a in (22.5, 202.5):
    ax.plot([0, 10 * np.cos(np.radians(a))], [0, 10 * np.sin(np.radians(a))], color=INK2, lw=1.4,
            ls=(0, (6, 4)), zorder=1)
ax.text(-4.7, 5.6, "WATCHER A", fontsize=17, weight="bold", color=WATCHER_COLOR["A"])
ax.text(-4.7, 5.05, "Batı · Kuzeybatı · Kuzey · Kuzeydoğu", fontsize=10, color=WATCHER_COLOR["A"])
ax.text(2.2, -5.3, "WATCHER B", fontsize=17, weight="bold", color=WATCHER_COLOR["B"])
ax.text(2.2, -5.85, "Doğu · Güneydoğu · Güney · Güneybatı", fontsize=10, color=WATCHER_COLOR["B"])

for r in (1, 2, 4):
    ax.add_patch(Circle((0, 0), r, fill=False, edgecolor=MUTED, lw=0.7, ls=(0, (2, 3)), zorder=1))
    a = np.radians(160)
    ax.text(r * np.cos(a), r * np.sin(a), f"{r} km", fontsize=8, color=MUTED, ha="center", va="center",
            bbox=dict(fc=WATCHER_TINT["A"], ec="none", pad=0.6), zorder=2)
ax.plot(0, 0, marker="*", ms=26, mfc=INK, mec=SURFACE, mew=1.5, zorder=6)
ax.text(0, -0.42, "BASE", fontsize=11, weight="bold", ha="center", va="top", zorder=6)

# track segments coloured by the level at the segment's end
for i in range(1, len(g)):
    ax.plot(g.x[i - 1:i + 1], g.y[i - 1:i + 1], color=LEVEL_COLOR[g.level[i]], lw=3.2,
            solid_capstyle="round", zorder=4)
# stops
stops = [(0, 8, "45 min stop"), (9, 12, "20 min stop"), (13, 21, "45 min stop")]
for a, b, lab in stops:
    px, py = g.x[a:b + 1].mean(), g.y[a:b + 1].mean()
    ax.add_patch(Circle((px, py), 0.22, facecolor=SURFACE, edgecolor=LEVEL_COLOR[g.level[b]], lw=2.4, zorder=5))
    ax.text(px + 0.32, py + 0.05, lab, fontsize=9, color=INK2, va="center", zorder=6)
# simulated continuation (tracker): straight line at last heading to the base
lx, ly = g.x.iloc[-1], g.y.iloc[-1]
ax.add_patch(FancyArrowPatch((lx, ly), (0.25 * lx, 0.25 * ly), arrowstyle="-|>", mutation_scale=18,
                             color=TRACKER, lw=2.2, ls=(0, (4, 3)), zorder=5))
# frame footprint + reports at the 14:10 spot
ax.add_patch(Rectangle((lx - 0.28, ly - 0.16), 0.56, 0.32, fill=False, edgecolor=INK, lw=1.4, zorder=6))
ax.text(lx - 0.25, ly - 0.3, "frame img_000860\n14:10: truck", fontsize=8.8, color=INK, ha="left", va="top",
        zorder=6, bbox=dict(fc=WATCHER_TINT["B"], ec="none", pad=0.8))
ax.annotate("✕ official reports 12:25 / 12:35 about this spot:\n\"our unit\", \"movements normal\"",
            xy=(lx - 0.1, ly + 0.17), xytext=(-0.6, 1.55), fontsize=8.8, color=LEVEL_COLOR["HIGH"],
            ha="left", va="bottom", zorder=7, arrowprops=dict(arrowstyle="-", color=LEVEL_COLOR["HIGH"], lw=0.8),
            bbox=dict(fc=SURFACE, ec="none", pad=1, alpha=0.9))

# numbered markers
def badge(axis, x, y, n, dx=0.0, dy=0.0):
    axis.add_patch(Circle((x + dx, y + dy), 0.3, facecolor=INK, edgecolor=SURFACE, lw=1.5, zorder=8))
    axis.text(x + dx, y + dy, str(n), fontsize=11, color=SURFACE, weight="bold", ha="center", va="center",
              zorder=9)


badge(ax, g.x[0], g.y[0], 1, dx=-0.65, dy=0.25)
badge(ax, g.x[8], g.y[8], 2, dx=-0.65, dy=-0.45)
badge(ax, g.x[13], g.y[13], 3, dx=-0.15, dy=0.55)
badge(ax, g.x[22], g.y[22], 4, dx=0.1, dy=0.6)
badge(ax, g.x[23], g.y[23], 5, dx=0.0, dy=0.6)
badge(ax, g.x[24], g.y[24], 6, dx=0.55, dy=0.45)
badge(ax, 0.45 * lx, 0.45 * ly, 7, dx=0.15, dy=-0.5)

# legend
lg = [("LOW", LEVEL_COLOR["LOW"]), ("MEDIUM", LEVEL_COLOR["MEDIUM"]), ("HIGH", LEVEL_COLOR["HIGH"])]
for i, (lab, c) in enumerate(lg):
    ax.plot([-6.6, -6.05], [-5.25 - i * 0.42] * 2, color=c, lw=3.2)
    ax.text(-5.9, -5.25 - i * 0.42, f"{lab} (watcher's level)", fontsize=9.5, va="center")
ax.plot([-6.6, -6.05], [-6.51] * 2, color=TRACKER, lw=2.2, ls=(0, (4, 3)))
ax.text(-5.9, -6.51, "Tracker, simulated", fontsize=9.5, va="center")

# ================= step cards =================
STEPS = [
    ("12:10–12:45", "A", "Watcher A · Kuzey Yolu",
     "T0122 parked 6 km north of the base.", "LOW. Only counted in the street state."),
    ("12:50", "A", "Watcher A → car registry",
     "Stop has lasted 45 min, inside 6 km.", "MEDIUM + note: \"parked 45 min, 6 km N\". Listed to supervisor."),
    ("12:55–13:55", "A", "Watcher A · Kuzeydoğu Kavşağı",
     "Hops 1.8 km, parks 20 min, hops 2.6 km, parks 45 min.\nStays ~5.5 km out while swinging from N to NE.",
     "MEDIUM + note: \"stop-and-go around the base\"."),
    ("14:00", "B", "Hand-off A → B · Doğu Yolu",
     "T0122 enters Watcher B's sector. B reads both notes\nand the full route so far from the registry.",
     "Keeps MEDIUM; watches closely."),
    ("14:05", "B", "Watcher B → supervisor",
     "5.34 → 4.11 km in 5 min (246 m/min), heading at the base.",
     "HIGH (1st tick): \"stop-and-go, now closing fast\"."),
    ("14:10", "S", "Frame + head supervisor",
     "img_000860: truck, 1.65 km, 492 m/min. HIGH holds (2nd tick).\n"
     "Official reports \"our unit\" / \"movements normal\" don't match:\n"
     "nothing was there at 12:25/12:35, and it is a truck, not a car → ignored.",
     "Dispatches a tracker; first alert goes to the operator."),
    ("14:10 →", "T", "Tracker (simulated) → authorities",
     "Heading 256° = straight at the base, 8.2 m/s.",
     "Position, speed and ETA (≈ 3 min) every tick, labelled SIMULATED."),
]
ACTOR = {"A": WATCHER_COLOR["A"], "B": WATCHER_COLOR["B"], "S": INK, "T": TRACKER}
cx = fig.add_axes([0.53, 0.29, 0.45, 0.62])
cx.axis("off"); cx.set_xlim(0, 1); cx.set_ylim(0, 1)
gap, LINE = 0.012, 0.021
y = 1.0
for n, (when, who, title, sees, does) in enumerate(STEPS, start=1):
    n_lines = sees.count("\n") + 1
    card_h = 0.094 + LINE * n_lines
    y0 = y - card_h
    cx.add_patch(FancyBboxPatch((0.0, y0), 1.0, card_h, boxstyle="round,pad=0,rounding_size=0.012",
                                facecolor=SURFACE, edgecolor=AXIS, lw=0.8))
    cx.add_patch(Rectangle((0.0, y0), 0.008, card_h, facecolor=ACTOR[who], edgecolor="none"))
    cx.add_patch(Circle((0.045, y - 0.032), 0.016, facecolor=INK, edgecolor="none",
                        transform=cx.transData))
    cx.text(0.045, y - 0.032, str(n), fontsize=10.5, color=SURFACE, weight="bold", ha="center", va="center")
    cx.text(0.075, y - 0.032, when, fontsize=11, weight="bold", va="center")
    cx.text(0.215, y - 0.032, title, fontsize=11, weight="bold", color=ACTOR[who], va="center")
    cx.text(0.075, y - 0.058, sees, fontsize=9.8, color=INK2, va="top", linespacing=1.3)
    cx.text(0.075, y - 0.058 - LINE * n_lines - 0.006, "→ " + does, fontsize=10, weight="bold", va="top")
    y = y0 - gap

# ================= timeline strip =================
tx = fig.add_axes([0.06, 0.06, 0.92, 0.17])
t0, t1 = g["min"].iloc[0], g["min"].iloc[-1] + 10
tx.set_xlim(t0 - 2, t1); tx.set_ylim(-0.3, 7)
# owner bands
bands = [(t0 - 2, 14 * 60 - 2.5, "A", "Watcher A owns T0122"), (14 * 60 - 2.5, 14 * 60 + 10, "B", "Watcher B"),
         (14 * 60 + 10, t1, "T", "Tracker")]
for a, b, w, lab in bands:
    col = WATCHER_TINT.get(w, "#ebe8f7")
    tx.axvspan(a, b, color=col, zorder=0)
    tx.text(a + 1.5, 3.2, lab, fontsize=9.5, weight="bold", color=ACTOR[w], va="center")
for r in (1, 2, 4):
    tx.axhline(r, color=MUTED, lw=0.6, ls=(0, (2, 3)), zorder=1)
for i in range(1, len(g)):
    tx.plot(g["min"][i - 1:i + 1], g.d[i - 1:i + 1], color=LEVEL_COLOR[g.level[i]], lw=3, zorder=3,
            solid_capstyle="round")
eta_min = g.d.iloc[-1] * 1000 / 8.2 / 60
tx.plot([t1 - 10, t1 - 10 + eta_min], [g.d.iloc[-1], 0], color=TRACKER, lw=2.2, ls=(0, (4, 3)), zorder=3)
for rt in ("12:25", "12:35"):
    m = int(rt[:2]) * 60 + int(rt[3:])
    tx.plot(m, 0.25, marker="x", ms=8, mew=2, color=LEVEL_COLOR["HIGH"], zorder=4)
tx.text(12 * 60 + 37, 0.25, "official reports at the 14:10 spot, contradicted", fontsize=8.5,
        color=LEVEL_COLOR["HIGH"], ha="left", va="center")
for n, i in [(1, 0), (2, 8), (3, 13), (4, 22), (5, 23), (6, 24)]:
    tx.text(g["min"][i], g.d[i] + 0.55, str(n), fontsize=9, weight="bold", ha="center", color=SURFACE,
            bbox=dict(boxstyle="circle,pad=0.25", fc=INK, ec="none"), zorder=5)
ticks = list(range(t0, t1 + 1, 15))
tx.set_xticks(ticks); tx.set_xticklabels([f"{m // 60:02d}:{m % 60:02d}" for m in ticks])
tx.set_yticks([0, 1, 2, 4, 6]); tx.set_ylabel("km to base", fontsize=10)
tx.tick_params(length=0, labelsize=9)
for s in ("top", "right"):
    tx.spines[s].set_visible(False)
tx.set_title("Distance to base over time: who owns the vehicle, and its level at each 5-min tick",
             loc="left", fontsize=12.5, weight="bold", pad=8)

fig.savefig(OUT, facecolor=PAGE)
print("wrote", OUT)
