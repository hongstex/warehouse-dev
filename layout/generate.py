"""面料仓货架布置草稿 v0 —— 生成 PNG / PDF / DXF 及仓位统计。

坐标单位 mm。原点 = 轴线 3-1 × 3-A；x 向东(3-1→3-13)，y 向北(3-A→3-D)。
底图依据《二~七层平面图》J-4改，核心筒/门/消火栓位置为读图估计，需现场复核。
"""
import json
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib import font_manager

OUT = Path(__file__).resolve().parent.parent / "output"

# ---------------- 建筑 ----------------
GRID_X = [i * 8000 for i in range(13)]          # 3-1 .. 3-13
GRID_Y = [0, 8000, 16000, 24000]                # 3-A .. 3-D
AXIS_X = [f"3-{i + 1}" for i in range(13)]
AXIS_Y = ["3-A", "3-B", "3-C", "3-D"]
COL = 600                                        # 柱截面(估)
INNER = (300, 300, 95700, 23700)                 # 室内净边界(扣外墙/边柱)

CORES = {  # 不可布置区域 (x0, y0, x1, y1)
    "T1 楼梯/货梯/前室": (0, 16000, 8000, 24000),
    "T2 前室": (32000, 20600, 37000, 24000),
    "T2 楼梯": (37000, 15800, 40000, 24000),
    "卫生间/前室": (40000, 15800, 48000, 24000),
    "T3 楼梯/货梯/前室": (88000, 16000, 96000, 24000),
}
SHUTTER_X = 48000                                # 防火卷帘 (3-7 轴, 3-A~3-C)
SHUTTER_BAND = (47000, 300, 49000, 16000)        # 卷帘两侧各 1m 净空

HYDRANTS = [  # 消火栓箱(读图估计)
    (23000, 300, 23700, 550), (72300, 300, 73000, 550),
    (23000, 23450, 23700, 23700), (72300, 23450, 73000, 23700),
    (300, 8750, 550, 9450), (95450, 8750, 95700, 9450),
    (40250, 15300, 40950, 15550), (48050, 16600, 48300, 17300),
]
DOORS = [  # 通往仓库的门(位置估计) (x, y, 说明)
    (8000, 21600, "T1前室门"), (32000, 22000, "T2前室门"),
    (88000, 21600, "T3前室门"), (10500, 0, "JM1a"), (12500, 24000, "JM1a"),
    (92000, 0, "JM1a"),
]

# ---------------- 货架参数 ----------------
SIDE = 1950        # 单排货架进深(外框)，放 140~180 幅宽布卷，卷轴垂直通道
FLUE = 100         # 背靠背间隙
CELL = 2000        # 单格沿通道方向宽度(柱距中心)
LEVELS = 2

# 货架排沿 y 向(南北)，通道南北向，E-W 主通道居中。
# x 向排布由 layout/optimize 结果固化；东区为西区关于 3-7 轴镜像。
WEST_ROWS = [  # (类型, x0)  S=单排靠墙/靠卷帘带, D=背靠背双排
    ("S", 300), ("D", 4300), ("D", 12000), ("D", 18000), ("D", 24000),
    ("D", 30000), ("D", 36300), ("D", 43000),
]
MAIN_AISLE = (10400, 13400)                     # 中部东西向主通道 3.0m
SLOTS_Y = [(400 + i * CELL, 400 + (i + 1) * CELL) for i in range(5)] + \
          [(13400 + i * CELL, 13400 + (i + 1) * CELL) for i in range(5)]

ZONES = {  # 功能区(不布货架)
    "收发暂存区 W\n(货梯出口)": (8300, 13400, 16000, 23700),
    "收发暂存区 E\n(货梯出口)": (80000, 13400, 87700, 23700),
    "验布/分拣/待上架\n(兼卫生间通道,待核实)": (48300, 13400, 53000, 23700),
    "T2前室门通道": (28000, 19400, 34000, 23700),
}
NO_RACK = [  # 额外禁布区：烟道/消火栓前方
    (0, 6500, 2300, 10400), (93700, 6500, 96000, 10400),
]


def mirror_rows(rows):
    out = []
    for kind, x0 in rows:
        w = SIDE if kind == "S" else 2 * SIDE + FLUE
        out.append((kind, 2 * SHUTTER_X - (x0 + w)))
    return out


def rack_sides():
    sides = []
    for kind, x0 in WEST_ROWS + mirror_rows(WEST_ROWS):
        if kind == "S":
            sides.append((x0, x0 + SIDE))
        else:
            sides += [(x0, x0 + SIDE), (x0 + SIDE + FLUE, x0 + 2 * SIDE + FLUE)]
    return sorted(sides)


def overlap(a, b, gap=0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def columns():
    return [(x - COL / 2, y - COL / 2, x + COL / 2, y + COL / 2) for x in GRID_X for y in GRID_Y]


def build_cells():
    blocks = list(CORES.values()) + list(ZONES.values()) + NO_RACK + [SHUTTER_BAND]
    cols = columns()
    cells = []
    for sx0, sx1 in rack_sides():
        for y0, y1 in SLOTS_Y:
            c = (sx0, y0, sx1, y1)
            if any(overlap(c, b) for b in blocks):
                continue
            if any(overlap(c, k, 50) for k in cols):
                continue
            cells.append(c)
    return cells


def stats(cells):
    west = [c for c in cells if c[2] <= SHUTTER_X]
    east = [c for c in cells if c[0] >= SHUTTER_X]
    floor = (INNER[2] - INNER[0]) * (INNER[3] - INNER[1]) / 1e6 - sum(
        (b[2] - b[0]) * (b[3] - b[1]) / 1e6 for b in CORES.values())
    foot = len(cells) * SIDE * CELL / 1e6
    return {
        "cells_per_level": len(cells),
        "positions_total": len(cells) * LEVELS,
        "west_compartment_positions": len(west) * LEVELS,
        "east_compartment_positions": len(east) * LEVELS,
        "usable_floor_m2": round(floor),
        "rack_footprint_m2": round(foot),
        "footprint_ratio": round(foot / floor, 3),
    }


# ---------------- 输出 ----------------
def cjk_font():
    for f in font_manager.findSystemFonts():
        if "wqy" in f.lower() or "noto" in f.lower() and "cjk" in f.lower():
            return font_manager.FontProperties(fname=f)
    return None


def draw_png(cells, st, path):
    fp = cjk_font()
    kw = {"fontproperties": fp} if fp else {}
    fig, ax = plt.subplots(figsize=(30, 9.5))
    ax.set_aspect("equal")
    ax.set_xlim(-4000, 100000)
    ax.set_ylim(-5500, 28500)
    ax.axis("off")
    for x, n in zip(GRID_X, AXIS_X):
        ax.plot([x, x], [-1500, 25500], color="#d33", lw=0.5, ls="-.")
        ax.text(x, -2600, n, ha="center", fontsize=9, **kw)
    for y, n in zip(GRID_Y, AXIS_Y):
        ax.plot([-1500, 97500], [y, y], color="#d33", lw=0.5, ls="-.")
        ax.text(-2600, y, n, va="center", ha="right", fontsize=9, **kw)
    ax.add_patch(Rectangle((0, 0), 96000, 24000, fill=False, lw=2.2, ec="#222"))
    for n, (x0, y0, x1, y1) in CORES.items():
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#bbb", ec="#555", hatch="//", lw=1))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, n, ha="center", va="center", fontsize=8, **kw)
    for n, (x0, y0, x1, y1) in ZONES.items():
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#fff3c4", ec="#c90", ls="--", lw=1))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, n, ha="center", va="center", fontsize=8, **kw)
    x0, y0, x1, y1 = SHUTTER_BAND
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#ffd6d6", ec="none"))
    ax.plot([SHUTTER_X, SHUTTER_X], [300, 16000], color="#e00", lw=2.5)
    ax.text(SHUTTER_X, 4000, "防火卷帘\n两侧各1m净空", ha="center", fontsize=8, color="#b00", rotation=90, **kw)
    ax.add_patch(Rectangle((300, MAIN_AISLE[0]), 95400, MAIN_AISLE[1] - MAIN_AISLE[0], fc="#e3f2ff", ec="none"))
    ax.text(20000, sum(MAIN_AISLE) / 2, "主通道 3.0m  ←→", ha="center", va="center", fontsize=10, color="#06c", **kw)
    ax.text(68000, sum(MAIN_AISLE) / 2, "主通道 3.0m  ←→", ha="center", va="center", fontsize=10, color="#06c", **kw)
    for c in cells:
        ax.add_patch(Rectangle((c[0], c[1]), c[2] - c[0], c[3] - c[1], fc="#7fb77e", ec="#2d5a2c", lw=0.6))
    for k in columns():
        ax.add_patch(Rectangle((k[0], k[1]), COL, COL, fc="#444", ec="none"))
    for h in HYDRANTS:
        ax.add_patch(Rectangle((h[0], h[1]), h[2] - h[0], h[3] - h[1], fc="#e00", ec="#e00"))
    for x, y, n in DOORS:
        ax.plot(x, y, marker="v" if y == 24000 else "^" if y == 0 else ">", color="#c0c", ms=9)
        ax.text(x, y + (900 if y == 0 else -1300 if y == 24000 else 600), n, fontsize=7, color="#a0a", ha="center", **kw)
    # 典型尺寸标注
    for a, b, y, t in [(300, 2250, 25200, "1.95"), (2250, 4300, 25200, "2.05"), (4300, 8300, 25200, "4.0"),
                       (8300, 12000, 25200, "3.7"), (12000, 16000, 25200, "4.0"), (16000, 18000, 25200, "2.0"),
                       (18000, 22000, 25200, "4.0"), (22000, 24000, 25200, "2.0")]:
        ax.annotate("", (a, y), (b, y), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.text((a + b) / 2, y + 250, t, ha="center", fontsize=7, **kw)
    title = (f"面料仓货架布置草稿 v0（二~七层标准层）  单格≈2.0×1.95m ×{LEVELS}层  "
             f"仓位 {st['positions_total']} 格（西区 {st['west_compartment_positions']} / 东区 {st['east_compartment_positions']}）  "
             f"货架占地率 {st['footprint_ratio']:.0%}")
    ax.text(0, 27200, title, fontsize=14, weight="bold", **kw)
    ax.text(0, -4600, "图例：绿=货架单格(每格2层)  灰斜线=核心筒  黄虚线=功能区  红块=消火栓(估)  "
            "紫箭头=门  浅蓝=主通道  粉=防火卷帘净空带   尺寸单位 m（标注）/mm（坐标）  ——草稿，柱/门/消火栓需现场复核",
            fontsize=9, **kw)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def draw_dxf(cells, path):
    doc = ezdxf.new("R2010", setup=True)
    doc.styles.add("CJK", font="simhei.ttf")
    for name, color in [("AXIS", 1), ("COLUMN", 8), ("CORE", 9), ("RACK", 3), ("ZONE", 2),
                        ("AISLE", 5), ("SHUTTER", 1), ("HYDRANT", 1), ("TEXT", 7)]:
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def rect(b, layer):
        msp.add_lwpolyline([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], close=True,
                           dxfattribs={"layer": layer})

    def text(s, x, y, h=350):
        msp.add_text(s, height=h, dxfattribs={"layer": "TEXT", "style": "CJK"}).set_placement(
            (x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    for x, n in zip(GRID_X, AXIS_X):
        msp.add_line((x, -1500), (x, 25500), dxfattribs={"layer": "AXIS"})
        text(n, x, -2200, 500)
    for y, n in zip(GRID_Y, AXIS_Y):
        msp.add_line((-1500, y), (97500, y), dxfattribs={"layer": "AXIS"})
        text(n, -2400, y, 500)
    for k in columns():
        rect(k, "COLUMN")
    for n, b in CORES.items():
        rect(b, "CORE"); text(n, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    for n, b in ZONES.items():
        rect(b, "ZONE"); text(n.replace("\n", " "), (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, 300)
    rect((300, MAIN_AISLE[0], 95700, MAIN_AISLE[1]), "AISLE")
    rect(SHUTTER_BAND, "SHUTTER")
    msp.add_line((SHUTTER_X, 300), (SHUTTER_X, 16000), dxfattribs={"layer": "SHUTTER"})
    for h in HYDRANTS:
        rect(h, "HYDRANT")
    for c in cells:
        rect(c, "RACK")
    doc.saveas(path)


def main():
    OUT.mkdir(exist_ok=True)
    cells = build_cells()
    st = stats(cells)
    draw_png(cells, st, OUT / "layout_v0.png")
    draw_dxf(cells, OUT / "layout_v0.dxf")
    (OUT / "layout_v0_stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=2))
    print(json.dumps(st, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
