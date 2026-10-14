"""5 楼面料仓货架布置 v1 —— 方案 A / B 布置、仓位、用料，输出网页数据和 PNG / PDF / DXF。

坐标单位 mm。原点 = 轴线 3-1 × 3-A；x 向东(3-1→3-13)，y 向北(3-A→3-D)。
底图依据《二~七层平面图》J-4改 及《五~七层局部平面图》；核心筒、门、消火栓位置为读图估计，需现场复核。

方案 A：南北向短排（垂直长边），人工爬梯，2.0m 通道。
方案 B：东西向通长排（平行长边，同 7 楼做法），每隔一段空一格做横向过道，2.3m 通道可走小叉车。
"""
import json
import math
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"          # Cloudflare Pages 发布目录
OUT = PUBLIC / "files"            # 下载文件 png/pdf/dxf
DATA = PUBLIC / "data"            # 网页渲染用 JSON
VERSION = "v1"

# ======================= 建筑（5 层） =======================
GRID_X = [i * 8000 for i in range(13)]          # 3-1 .. 3-13
GRID_Y = [0, 8000, 16000, 24000]                # 3-A .. 3-D
AXIS_X = [f"3-{i + 1}" for i in range(13)]
AXIS_Y = ["3-A", "3-B", "3-C", "3-D"]
COL = 600                                        # 柱截面(估)
FLOOR_H = 4300                                   # 层高
X_MIN, X_MAX, Y_MIN, Y_MAX = 300, 95700, 300, 23700   # 室内净边界(扣边柱)

CORES = {  # 不可布置区域 (x0, y0, x1, y1)
    "T1 楼梯/货梯/前室": (0, 16000, 8000, 24000),
    "T2 前室": (32000, 20600, 37000, 24000),
    "T2 楼梯": (37000, 15800, 40000, 24000),
    "卫生间/前室": (40000, 15800, 48000, 24000),
    "T3 楼梯/货梯/前室": (88000, 16000, 96000, 24000),
}
SHUTTER_X = 48000                                # 防火卷帘 (3-7 轴, 3-A~3-C)
SHUTTER_BAND = (47000, 300, 49000, 16000)        # 卷帘两侧各 1m 净空，兼作过道
HYDRANTS = [  # 消火栓箱(读图估计)
    (23000, 300, 23700, 550), (72300, 300, 73000, 550),
    (23000, 23450, 23700, 23700), (72300, 23450, 73000, 23700),
    (300, 8750, 550, 9450), (95450, 8750, 95700, 9450),
    (40250, 15300, 40950, 15550), (48050, 16600, 48300, 17300),
]
NO_RACK = [(0, 6500, 2300, 10400), (93700, 6500, 96000, 10400)]   # 烟道/消火栓前方
DOORS = [  # (x, y, 说明)
    (8000, 21600, "T1货梯前室"), (32000, 22000, "T2前室"), (88000, 21600, "T3货梯前室"),
    (10500, 0, "JM1a"), (13600, 24000, "JM1a"), (91200, 0, "JM2"),
]

# ======================= 货架 =======================
CELL = 2000          # 单格沿排方向中心距
SIDE = 1950          # 单排进深(外框)
FLUE = 100           # 背靠背间隙
TUBE = 50            # 主材 50×50×2.5 方管（已确认；网页下拉可切换其它规格对比）
LEVELS = 2
BEAM_Z = [150, 2000]          # 各层承货面标高(梁顶)，螺栓孔距 50 可调
POST_H = 3800                 # 立柱高度(需复核梁底/喷头净空)
ACCESS = 1000                 # 货架取货面前方至少 1m 不得是核心筒

ROLL_D = (350, 400)           # 布卷外径范围
ROLL_KG = (20, 30)


def rolls_per_level(d):
    clear_w = CELL - TUBE                                  # 1920
    clear_h = BEAM_Z[1] - BEAM_Z[0] - TUBE                 # 1770
    return (clear_w // d) * (clear_h // d)


# ======================= 方案定义 =======================
SCHEMES = {
    "A": {
        "name": "方案 A · 南北向短排",
        "desc": "货架垂直长边，通道尽端对窗；2.0m 通道，适合人工爬梯。",
        "orient": "y",          # 排沿 y 向
        "aisle": 2000,
        "main_aisle": (300, 10400, 95700, 13400),
        # 每个货架面: (x0, x1, 取货面方向)；西区排位见 optimize_rows.py，东区镜像
        "west_rows": [("S", 300), ("D", 4300), ("D", 12000), ("D", 18000), ("D", 24000),
                      ("D", 30000), ("D", 36300), ("D", 43000)],
        "spans": [(400, 10400), (13400, 23700)],       # 排的 y 范围(主通道两侧)
        "zones": {
            "收发暂存 W": (8300, 13400, 16000, 23700),
            "收发暂存 E": (80000, 13400, 87700, 23700),
            "验布/分拣": (87700, 300, 91700, 10400),
            "办公室": (91700, 2500, 95700, 8400),
            "缓冲/待上架": (48300, 13400, 53000, 23700),
            "T2前室门通道": (28000, 19400, 34000, 23700),
        },
        "passages": [],
    },
    "B": {
        "name": "方案 B · 东西向通长排（同 7 楼）",
        "desc": "货架平行长边，沿主通道连绵布置，每隔一段空一格做横向过道；2.3m 通道可走小叉车。",
        "orient": "x",
        "aisle": 2300,
        "main_aisle": (300, 12800, 95700, 15450),
        # 每排: (y0, y1, 取货面) 自南向北
        "rows": [
            (300, 2250, "N"),                  # R1 南墙单排
            (4550, 6500, "S"),                 # R2 双排南面
            (6600, 8550, "N"),                 # R3 双排北面(含 3-B 柱)
            (10850, 12800, "NS"),              # R4 主通道旁单排，两面可取
            (15450, 17400, "S"),               # R5 双排南面(含 3-C 柱)
            (17500, 19450, "N"),               # R6 双排北面
            (21750, 23700, "S"),               # R7 北墙单排
        ],
        "aisles": [(2250, 4550), (8550, 10850), (12800, 15450), (19450, 21750)],
        "zones": {
            "收发暂存 W": (8300, 15450, 16000, 23700),
            "收发暂存 E": (80000, 15450, 87700, 23700),
            "验布/分拣": (80300, 300, 93700, 4550),
            "办公室": (87700, 4550, 93700, 10850),
            "T2前室门通道": (28000, 19450, 32000, 23700),
            "卫生间通道(待核实)": (49000, 15450, 51000, 23700),
        },
        # 横向过道：空出一格宽，贯通各排
        "passages": [(300, 300, 2300, 16000), (93700, 300, 95700, 16000),
                     (21700, 300, 23700, 23700), (72300, 300, 74300, 23700)],
    },
}


def mirror_rows(rows):
    out = []
    for kind, x0 in rows:
        w = SIDE if kind == "S" else 2 * SIDE + FLUE
        out.append((kind, 2 * SHUTTER_X - (x0 + w)))
    return out


def a_sides():
    """方案 A 货架面: (x0, x1, 取货面)。"""
    sides = []
    west = SCHEMES["A"]["west_rows"]
    for i, (kind, x0) in enumerate(west + mirror_rows(west)):
        east = i >= len(west)
        if kind == "S":
            sides.append((x0, x0 + SIDE, "W" if east else "E"))
        else:
            sides += [(x0, x0 + SIDE, "W"), (x0 + SIDE + FLUE, x0 + 2 * SIDE + FLUE, "E")]
    return sorted(sides)


def overlap(a, b, gap=0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def columns():
    return [(x - COL / 2, y - COL / 2, x + COL / 2, y + COL / 2) for x in GRID_X for y in GRID_Y]


def access_strips(c, face):
    x0, y0, x1, y1 = c
    s = []
    if "N" in face: s.append((x0, y1, x1, y1 + ACCESS))
    if "S" in face: s.append((x0, y0 - ACCESS, x1, y0))
    if "E" in face: s.append((x1, y0, x1 + ACCESS, y1))
    if "W" in face: s.append((x0 - ACCESS, y0, x0, y1))
    return s


def place_cells(key):
    """沿每排贪心布格：遇柱/核心筒/功能区/过道即跳过，取货面前方须可达。"""
    sc = SCHEMES[key]
    hard = list(CORES.values()) + list(sc["zones"].values()) + NO_RACK + [SHUTTER_BAND] + sc["passages"]
    cols = columns()
    cores = list(CORES.values())

    # 柱子只在排方向留 50mm 安装间隙；进深方向货架可贴柱面(如靠墙排贴边柱)
    ax = 0 if sc["orient"] == "x" else 1
    cols = [tuple(k[i] - 50 * (i % 2 == ax) if i < 2 else k[i] + 50 * (i % 2 == ax) for i in range(4))
            for k in cols]

    def ok(c, face):
        if any(overlap(c, b) for b in hard) or any(overlap(c, k) for k in cols):
            return False
        strips = access_strips(c, face)
        return any(not any(overlap(s, b) for b in cores) for s in strips)

    rows = []   # 每排: dict(face, cells=[rect])
    if sc["orient"] == "y":
        for x0, x1, face in a_sides():
            for lo, hi in sc["spans"]:
                cells, y = [], lo
                while y + CELL <= hi:
                    c = (x0, y, x1, y + CELL)
                    if ok(c, face):
                        cells.append(c); y += CELL
                    else:
                        y += 50
                rows.append({"face": face, "cells": cells, "axis": "y"})
    else:
        for y0, y1, face in sc["rows"]:
            cells, x = [], X_MIN
            while x + CELL <= X_MAX:
                c = (x, y0, x + CELL, y1)
                if ok(c, face):
                    cells.append(c); x += CELL
                else:
                    x += 50
            rows.append({"face": face, "cells": cells, "axis": "x"})
    return rows


def runs_of(rows):
    """连续相接的格组成一段货架(一个独立框架)。"""
    runs = []
    for r in rows:
        ax = 0 if r["axis"] == "x" else 1
        cur = []
        for c in r["cells"]:
            if cur and c[ax] != cur[-1][ax + 2]:
                runs.append((cur, r)); cur = []
            cur.append(c)
        if cur:
            runs.append((cur, r))
    out = []
    for cells, r in runs:
        out.append({
            "rect": [min(c[0] for c in cells), min(c[1] for c in cells),
                     max(c[2] for c in cells), max(c[3] for c in cells)],
            "n": len(cells), "axis": r["axis"], "face": r["face"],
        })
    return out


def code_cells(key, rows):
    """仓位编码 分区-排-格：W/E 区；排号 A 自西向东、B 自南向北；格号 A 自南向北、B 自西向东。"""
    out = []
    for zone in ("W", "E"):
        zrows = [[c for c in r["cells"] if (c[2] <= SHUTTER_X) == (zone == "W")] for r in rows]
        # 同一货架面(同 x 或同 y 位置)合并为一排
        groups = {}
        for r, cells in zip(rows, zrows):
            for c in cells:
                k = (c[0], c[2]) if r["axis"] == "y" else (c[1], c[3])
                groups.setdefault(k, []).append((c, r["face"]))
        for ri, k in enumerate(sorted(groups), 1):
            cells = sorted(groups[k], key=lambda t: (t[0][1], t[0][0]))
            for ci, (c, face) in enumerate(cells, 1):
                out.append({"code": f"{zone}-{ri:02d}-{ci:02d}", "rect": list(c), "face": face})
    return out


# ======================= 用料 =======================
STEEL = 7850e-9  # kg/mm³


def rhs_kg_m(b, h, t):
    return (2 * (b + h) - 4 * t) * t * STEEL * 1000


MATERIALS = {  # key: (名称, 规格, 单位, 单重kg)
    "post":  ("立柱", "方管 50×50×2.5", "根", None),
    "beam":  ("前后承货梁", "方管 50×50×2.5", "根", None),
    "cross": ("层间横撑(进深向)", "方管 50×50×2.5", "根", None),
    "mid":   ("中间托梁", "矩管 60×40×2", "根", None),
    "diag":  ("侧片斜撑", "方管 40×40×2", "根", None),
    "xbr":   ("背面剪刀撑", "方管 40×40×2", "根", None),
    "tie":   ("背靠背连接/顶拉杆", "方管 40×40×2 L=300", "根", None),
    "base":  ("立柱底座", "底板 120×120×6 + L50 连接角码", "套", 1.1),
    "anchor": ("地钉(膨胀螺栓)", "M12×100 机械锚栓", "套", None),
    "angle": ("梁端角码", "L50×50×5 L=80 冲孔", "个", 0.30),
    "clip":  ("托梁卡件", "U 型卡 / 小角码", "个", 0.15),
    "bolt":  ("螺栓", "M10×80 8.8 级 + 螺母 + 2 垫片", "套", None),
    "sleeve": ("防压套管", "Φ16×2.5 钢管 L=50", "个", 0.04),
    "bolt_s": ("螺栓(斜撑)", "M8×100 + 螺母 + 垫片", "套", None),
}
LEN = {  # 单件长度 mm
    "post": POST_H, "beam": CELL - TUBE, "cross": SIDE - 2 * TUBE, "mid": CELL - TUBE,
    "diag": round(math.hypot(SIDE - 2 * TUBE, BEAM_Z[1])), "xbr": round(math.hypot(CELL, BEAM_Z[1])),
    "tie": 300,
}
KG_M = {"6040": rhs_kg_m(60, 40, 2), "40": rhs_kg_m(40, 40, 2), "50": rhs_kg_m(50, 50, 2.5)}
SECTION = {"post": "50", "beam": "50", "cross": "50", "mid": "6040", "diag": "40", "xbr": "40", "tie": "40"}
XBR_EVERY = 4    # 每 4 格设一道背面剪刀撑(2 根)


def back_to_back(runs):
    """每段货架背面 FLUE 处是否有另一段货架(背靠背需拉结)。返回需拉结的立柱列数。"""
    lines = 0
    for r in runs:
        x0, y0, x1, y1 = r["rect"]
        if r["axis"] == "x":
            probe = (x0, y0 - FLUE - 10, x1, y0) if "N" == r["face"] else None
        else:
            probe = (x1, y0, x1 + FLUE + 10, y1) if "W" == r["face"] else None
        if probe and any(o is not r and overlap(probe, o["rect"]) for o in runs):
            lines += r["n"] + 1
    return lines


def bom(runs):
    q = {k: 0 for k in MATERIALS}
    for r in runs:
        n = r["n"]
        lines = n + 1                       # 立柱列数(每列前后 2 根)
        q["post"] += 2 * lines
        q["beam"] += 2 * n * LEVELS
        q["mid"] += 2 * n * LEVELS
        q["cross"] += lines * (LEVELS + 1)  # 每层 1 根 + 柱顶 1 根，组成侧片
        q["diag"] += 2 * lines
        q["xbr"] += 2 * math.ceil(n / XBR_EVERY)
        q["base"] += 2 * lines
        q["anchor"] += 4 * lines
        q["angle"] += 2 * (2 * n * LEVELS) + 2 * (lines * (LEVELS + 1))   # 承货梁两端 + 横撑两端
        q["clip"] += 2 * (2 * n * LEVELS)
        q["bolt_s"] += 2 * (2 * lines) + 2 * (2 * math.ceil(n / XBR_EVERY))   # 斜撑/剪刀撑两端
    q["tie"] = 2 * back_to_back(runs)      # 每列中部 + 顶部各 1
    q["bolt"] = 4 * q["angle"] + 2 * q["base"] + 2 * q["tie"]
    q["sleeve"] = q["bolt"]                # 每个 M10 过管处 1 个套管，防止拧紧压扁 50 方管

    items = []
    total_kg = 0.0
    for k, (name, spec, unit, unit_kg) in MATERIALS.items():
        if k in LEN:
            kgm = KG_M[SECTION[k]]
            unit_kg = kgm * LEN[k] / 1000
        kg = (unit_kg or 0) * q[k]
        total_kg += kg
        items.append({"key": k, "name": name, "spec": spec, "unit": unit, "qty": q[k],
                      "len_mm": LEN.get(k), "unit_kg": round(unit_kg, 2) if unit_kg else None,
                      "kg": round(kg)})
    # 6m 定尺下料(首次适应递减，锯缝 3mm)
    stock = {}
    for sec, label in (("6040", "矩管 60×40×2"), ("40", "方管 40×40×2"), ("50", "方管 50×50×2.5")):
        pieces = []
        for k, s in SECTION.items():
            if s == sec:
                pieces += [LEN[k]] * q[k]
        bars = []
        for p in sorted(pieces, reverse=True):
            for i, rem in enumerate(bars):
                if rem >= p + 3:
                    bars[i] = rem - p - 3
                    break
            else:
                bars.append(6000 - p - 3)
        total_len = sum(pieces) / 1000
        stock[label] = {"bars_6m": len(bars), "net_m": round(total_len),
                        "usage": round(total_len / (len(bars) * 6) if bars else 0, 3),
                        "kg": round(len(bars) * 6 * KG_M[sec])}
    return {"items": items, "net_kg": round(total_kg), "stock_6m": stock,
            "kg_per_m": {k: round(v, 2) for k, v in KG_M.items()}}


# ======================= 统计 =======================
def stats(cells, runs):
    west = [c for c in cells if c["rect"][2] <= SHUTTER_X]
    floor = (X_MAX - X_MIN) * (Y_MAX - Y_MIN) / 1e6 - sum(
        (b[2] - b[0]) * (b[3] - b[1]) / 1e6 for b in CORES.values())
    foot = len(cells) * SIDE * CELL / 1e6
    lo, hi = rolls_per_level(ROLL_D[1]), rolls_per_level(ROLL_D[0])
    pos = len(cells) * LEVELS
    cell_kg_max = hi * ROLL_KG[1] * LEVELS
    return {
        "cells_per_level": len(cells),
        "positions_total": pos,
        "west_positions": len(west) * LEVELS,
        "east_positions": (len(cells) - len(west)) * LEVELS,
        "runs": len(runs),
        "usable_floor_m2": round(floor),
        "rack_footprint_m2": round(foot),
        "footprint_ratio": round(foot / floor, 3),
        "rolls_per_level": [lo, hi],
        "rolls_total": [pos * lo, pos * hi],
        "cell_load_kg_max": cell_kg_max,
        "rack_load_kn_m2_max": round(cell_kg_max * 9.81 / 1000 / (SIDE * CELL / 1e6), 1),
        "floor_avg_kn_m2": round(pos * (lo + hi) / 2 * sum(ROLL_KG) / 2 * 9.81 / 1000 / floor, 2),
        "elevator_trips_full": [math.ceil(pos * lo / 40), math.ceil(pos * hi / 40)],
    }


def build(key):
    sc = SCHEMES[key]
    rows = place_cells(key)
    runs = runs_of(rows)
    cells = code_cells(key, rows)
    return {
        "key": key, "name": sc["name"], "desc": sc["desc"], "version": VERSION, "units": "mm",
        "levels": LEVELS, "aisle": sc["aisle"], "orient": sc["orient"],
        "rack": {"cell": CELL, "side": SIDE, "flue": FLUE, "tube": TUBE, "beam_z": BEAM_Z,
                 "post_h": POST_H, "roll_d": ROLL_D, "roll_kg": ROLL_KG},
        "floor_h": FLOOR_H, "outline": [0, 0, 96000, 24000],
        "grid": {"x": [[v, n] for v, n in zip(GRID_X, AXIS_X)], "y": [[v, n] for v, n in zip(GRID_Y, AXIS_Y)]},
        "columns": columns(),
        "cores": [{"name": n, "rect": list(b)} for n, b in CORES.items()],
        "zones": [{"name": n, "rect": list(b)} for n, b in sc["zones"].items()],
        "passages": [list(p) for p in sc["passages"]],
        "mainAisle": list(sc["main_aisle"]),
        "shutter": {"x": SHUTTER_X, "y": [300, 16000], "band": list(SHUTTER_BAND)},
        "hydrants": [list(h) for h in HYDRANTS],
        "doors": [{"x": x, "y": y, "name": n} for x, y, n in DOORS],
        "cells": cells,
        "runs": runs,
        "stats": stats(cells, runs),
        "bom": bom(runs),
    }


# ======================= 输出 =======================
def cjk_font():
    for f in font_manager.findSystemFonts():
        low = f.lower()
        if "wqy" in low or ("noto" in low and "cjk" in low):
            return font_manager.FontProperties(fname=f)
    return None


def draw_png(d, path):
    fp = cjk_font()
    kw = {"fontproperties": fp} if fp else {}
    fig, ax = plt.subplots(figsize=(30, 9.5))
    ax.set_aspect("equal"); ax.set_xlim(-4000, 100000); ax.set_ylim(-5500, 28500); ax.axis("off")
    for x, n in zip(GRID_X, AXIS_X):
        ax.plot([x, x], [-1500, 25500], color="#d33", lw=0.5, ls="-.")
        ax.text(x, -2600, n, ha="center", fontsize=9, **kw)
    for y, n in zip(GRID_Y, AXIS_Y):
        ax.plot([-1500, 97500], [y, y], color="#d33", lw=0.5, ls="-.")
        ax.text(-2600, y, n, va="center", ha="right", fontsize=9, **kw)
    ax.add_patch(Rectangle((0, 0), 96000, 24000, fill=False, lw=2.2, ec="#222"))
    m = d["mainAisle"]
    ax.add_patch(Rectangle((m[0], m[1]), m[2] - m[0], m[3] - m[1], fc="#e3f2ff", ec="none"))
    for p in d["passages"]:
        ax.add_patch(Rectangle((p[0], p[1]), p[2] - p[0], p[3] - p[1], fc="#eef6ff", ec="#9cc3e6", ls=":", lw=0.8))
    for c in d["cores"]:
        x0, y0, x1, y1 = c["rect"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#bbb", ec="#555", hatch="//", lw=1))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, c["name"], ha="center", va="center", fontsize=8, **kw)
    for z in d["zones"]:
        x0, y0, x1, y1 = z["rect"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#fff3c4", ec="#c90", ls="--", lw=1))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, z["name"], ha="center", va="center", fontsize=8, **kw)
    x0, y0, x1, y1 = SHUTTER_BAND
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#ffd6d6", ec="none"))
    ax.plot([SHUTTER_X, SHUTTER_X], [300, 16000], color="#e00", lw=2.5)
    for c in d["cells"]:
        r = c["rect"]
        ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc="#7fb77e", ec="#2d5a2c", lw=0.6))
    for k in d["columns"]:
        ax.add_patch(Rectangle((k[0], k[1]), COL, COL, fc="#444", ec="none"))
    for h in HYDRANTS:
        ax.add_patch(Rectangle((h[0], h[1]), h[2] - h[0], h[3] - h[1], fc="#e00", ec="#e00"))
    for o in d["doors"]:
        ax.plot(o["x"], o["y"], marker="o", color="#c0c", ms=7)
        ax.text(o["x"], o["y"] + (900 if o["y"] == 0 else -1300 if o["y"] == 24000 else 600), o["name"],
                fontsize=7, color="#a0a", ha="center", **kw)
    st = d["stats"]
    title = (f"5 楼面料仓 {d['name']}（{VERSION}）  通道 {d['aisle'] / 1000:.1f}m  "
             f"仓位 {st['positions_total']} 格（西 {st['west_positions']} / 东 {st['east_positions']}）  "
             f"约 {st['rolls_total'][0]}~{st['rolls_total'][1]} 卷  货架占地率 {st['footprint_ratio']:.0%}")
    ax.text(0, 27200, title, fontsize=14, weight="bold", **kw)
    ax.text(0, -4600, "绿=货架单格(每格2层)  灰斜线=核心筒  黄虚线=功能区  浅蓝=主通道/横向过道  粉=防火卷帘净空  "
            "红块=消火栓(估)  紫点=门   ——草稿，柱/门/消火栓需现场复核", fontsize=9, **kw)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def draw_dxf(d, path):
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
        msp.add_line((x, -1500), (x, 25500), dxfattribs={"layer": "AXIS"}); text(n, x, -2200, 500)
    for y, n in zip(GRID_Y, AXIS_Y):
        msp.add_line((-1500, y), (97500, y), dxfattribs={"layer": "AXIS"}); text(n, -2400, y, 500)
    for k in d["columns"]:
        rect(k, "COLUMN")
    for c in d["cores"]:
        b = c["rect"]; rect(b, "CORE"); text(c["name"], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    for z in d["zones"]:
        b = z["rect"]; rect(b, "ZONE"); text(z["name"], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, 300)
    rect(d["mainAisle"], "AISLE")
    for p in d["passages"]:
        rect(p, "AISLE")
    rect(SHUTTER_BAND, "SHUTTER")
    msp.add_line((SHUTTER_X, 300), (SHUTTER_X, 16000), dxfattribs={"layer": "SHUTTER"})
    for h in HYDRANTS:
        rect(h, "HYDRANT")
    for c in d["cells"]:
        rect(c["rect"], "RACK")
        b = c["rect"]; text(c["code"], (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, 180)
    doc.saveas(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    summary = {}
    for key in SCHEMES:
        d = build(key)
        tag = f"5F_{key}_{VERSION}"
        draw_png(d, OUT / f"layout_{tag}.png")
        draw_dxf(d, OUT / f"layout_{tag}.dxf")
        (DATA / f"layout_{key}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
        summary[key] = {**d["stats"], "steel_kg": d["bom"]["net_kg"],
                        "bars_50x50x2.5_6m": d["bom"]["stock_6m"]["方管 50×50×2.5"]["bars_6m"]}
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
