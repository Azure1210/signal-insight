#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : layers.py
# @Path       : signal-insight/src/signal_insight/viz/layers.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15 20:00:00
# @Version    : v1.1.0
# @Description: 地图的数据层（六边形热力、气泡、流向、小多图）和放大图配件（放大框、按米画圆、定位小图、色条）
# @ChangeLog:
#   2026-10-15 20:00:00 | Matri | v1.0.0 | 从 D3_05 抽出六边形热力和放大图配件；新增气泡、流向、小多图
#   2026-10-16 10:00:00 | Matri | v1.1.0 | facets 支持 min_value / small（小样本抑制），被藏的数不参与色阶、不当"最多的区"

"""地图的数据层和配件。实现放在这里，入口挂在 Regions 上（geo.hexbin / geo.bubbles / geo.flows / geo.facets /
geo.locator），和 fill / points / label 一样"往调用方给的 ax 上加一层，返回 matplotlib 对象"。
不依赖区界的几样（zoom / circle / colorbar / hexgrid）是模块级函数，由 maps 重新导出：viz.maps.zoom(...)。

和 maps.py 分开放，是因为改动原因不同（AGENTS.md 第 2 条）：maps 管边界和标注排版，这里管"数据怎么画成图形"。
本模块不 import maps（maps import 本模块）：需要区界的函数，第一个参数收 Regions 对象。
颜色都从 viz.maps.colors 取（heat_low / heat_mid / heat_high / small / hot / line / ink），不读 theme。

距离一律按米：格宽、圆半径、放大框都给米，经纬两个方向分别折算，配上长宽比校正画出来是正六边形、正圆、正方形。
"""
from __future__ import annotations

import math
import warnings
from types import SimpleNamespace
from typing import Iterable, Mapping

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects as pe
from matplotlib.collections import PatchCollection, PolyCollection
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch, Ellipse, FancyArrowPatch, PathPatch, Rectangle
from matplotlib.path import Path
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

from .callouts import FURNITURE
from .mapcolors import colors as MC

__all__ = ["M_PER_DEG", "HALO", "m2deg", "nice_size", "heat_cmap", "hexgrid", "colorbar", "circle", "zoom"]

M_PER_DEG = 111_320.0                        # 纬度 1 度 ≈ 111.32 公里；经度 1 度再乘 cos(纬度)
HALO = [pe.withStroke(linewidth=2.6, foreground="white")]   # 文字白边：压在填色、气泡上也看得清
_NICE_M = (50, 100, 200, 250, 500, 1_000, 2_000, 2_500, 5_000, 10_000, 20_000, 25_000, 50_000)
_HOWS = ("count", "nunique", "max", "sum", "mean")


# ── 单位 ─────────────────────────────────────────────────────────────────
def m2deg(m: float, lat0: float) -> tuple[float, float]:
    """米 → (经度差, 纬度差)。"""
    return m / (M_PER_DEG * math.cos(math.radians(lat0))), m / M_PER_DEG


def _to_m(lng, lat, origin, lat0):
    k = math.cos(math.radians(lat0))
    return (np.asarray(lng, float) - origin[0]) * k * M_PER_DEG, (np.asarray(lat, float) - origin[1]) * M_PER_DEG


def _to_deg(x, y, origin, lat0):
    k = math.cos(math.radians(lat0))
    return origin[0] + np.asarray(x) / (k * M_PER_DEG), origin[1] + np.asarray(y) / M_PER_DEG


def nice_size(span_m: float, n: int = 40) -> int:
    """视窗宽 span_m 米、横向约 n 格时的格宽，取 _NICE_M 里按倍数最接近的（500 米、2.5 公里这类）。"""
    target = span_m / n
    return min(_NICE_M, key=lambda s: abs(math.log(s / target)))


def heat_cmap() -> LinearSegmentedColormap:
    """热力色阶：colors.heat_low → heat_mid → heat_high（默认主色浅 → 深，规范第 2 节：单色渐变，不用彩虹）。"""
    return LinearSegmentedColormap.from_list("heat", [MC.heat_low, MC.heat_mid, MC.heat_high])


# ── 六边形网格（尖顶朝上），轴向坐标 (q, r) ─────────────────────────────────
def _axial(x, y, w):
    """平面米 → 所在格 (q, r)。w = 对边距离（= 相邻格中心距离），外接圆半径 R = w / √3。立方坐标取整。"""
    R = w / math.sqrt(3)
    qf = (math.sqrt(3) / 3 * x - y / 3) / R
    rf = (2 / 3 * y) / R
    sf = -qf - rf
    q, r, s = np.round(qf), np.round(rf), np.round(sf)
    dq, dr, ds = np.abs(q - qf), np.abs(r - rf), np.abs(s - sf)
    fix_q = (dq > dr) & (dq > ds)
    fix_r = ~fix_q & (dr > ds)
    q = np.where(fix_q, -r - s, q)
    r = np.where(fix_r, -q - s, r)
    return q.astype(np.int64), r.astype(np.int64)


def _center(q, r, w):
    return w * (np.asarray(q) + np.asarray(r) / 2), w * math.sqrt(3) / 2 * np.asarray(r)


def _hex_verts(cx, cy, w):
    """格中心 → 六个顶点 (N, 6, 2)，平面米。"""
    R = w / math.sqrt(3)
    a = np.radians(30 + 60 * np.arange(6))
    return np.stack([np.asarray(cx)[:, None] + R * np.cos(a), np.asarray(cy)[:, None] + R * np.sin(a)], axis=-1)


def hexgrid(df: pd.DataFrame, size_m: float, *, lng: str = "lng", lat: str = "lat", value: str | None = None,
            how: str = "count", min_value: float | None = 5, origin: tuple[float, float] | None = None,
            lat0: float | None = None) -> pd.DataFrame:
    """只统计不画：每格一行，按 value 从大到小。

    列：q, r（格编号）、lng, lat（格中心）、value（按 how 聚合）、n_rows（落进格子的行数）、suppressed（value < min_value）。
    df.attrs 记着 size_m / origin / lat0 / how / value / min_value。
    how："count" 行数 | "nunique" value 列去重（value="imsi"：一人只算一次）| "max" | "sum" | "mean"。
    origin：网格原点 (lng, lat)，不给 = 数据中心取整到 0.1°。几张图要格子严格对齐就传同一个。
    """
    if how not in _HOWS:
        raise ValueError(f"how 只能是 {_HOWS}，拿到 {how!r}")
    if how != "count" and value is None:
        raise ValueError(f"how={how!r} 要给 value（按哪一列聚合）")
    if not size_m or size_m <= 0:
        raise ValueError(f"size_m 是格宽（米），要大于 0，拿到 {size_m!r}")
    cols = ["q", "r", "lng", "lat", "value", "n_rows", "suppressed"]
    df = df.dropna(subset=[lng, lat])
    if df.empty:
        out = pd.DataFrame({c: pd.Series(dtype=float) for c in cols})
    else:
        g = df.groupby([lng, lat], sort=False).ngroup().to_numpy()   # 先按"不同坐标"算格号：几十万行信令只有几千个站
        uc = df[[lng, lat]].drop_duplicates()
        if origin is None:
            origin = (round(float(uc[lng].mean()), 1), round(float(uc[lat].mean()), 1))
        lat0 = origin[1] if lat0 is None else lat0
        q, r = _axial(*_to_m(uc[lng], uc[lat], origin, lat0), size_m)
        grp = pd.DataFrame({"q": q[g], "r": r[g], "v": df[value].to_numpy() if value else 1}).groupby(["q", "r"])["v"]
        out = pd.DataFrame({"value": grp.size() if how == "count" else grp.agg(how), "n_rows": grp.size()}).reset_index()
        out["lng"], out["lat"] = _to_deg(*_center(out["q"], out["r"], size_m), origin, lat0)
        out["suppressed"] = (out["value"] < min_value) if min_value is not None else False
        out = out[cols].sort_values("value", ascending=False, ignore_index=True)
    out.attrs.update(size_m=size_m, origin=origin, lat0=lat0, how=how, value=value, min_value=min_value)
    return out


# ── 区界的几何（Regions 里已经定好方向的环：外环逆时针、洞顺时针）────────────────
def _union_path(rings: list[np.ndarray]) -> Path:
    verts, codes = [], []
    for r in rings:
        verts += [*r, r[0]]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(r) - 1) + [Path.CLOSEPOLY]
    return Path(np.asarray(verts), codes)


def _inside_any(rings: list[np.ndarray], pts: np.ndarray) -> np.ndarray:
    """落在任一区内（洞里不算）：环绕数 = 外环包含次数 − 洞包含次数 > 0。"""
    wind = np.zeros(len(pts), int)
    for r in rings:
        ccw = (np.dot(r[:, 0], np.roll(r[:, 1], -1)) - np.dot(r[:, 1], np.roll(r[:, 0], -1))) > 0
        wind += np.where(Path(r).contains_points(pts), 1 if ccw else -1, 0)
    return wind > 0


def _all_rings(geo) -> list[np.ndarray]:
    return [r for rings in geo._rings.values() for r in rings]


def _make_norm(norm, vals: np.ndarray, lo_floor: float | None, vmax: float | None) -> Normalize:
    """"log"：下限 = lo_floor（门槛 5，色条从门槛起）或最小正数；"linear"：从 0 起；Normalize 原样用。"""
    if isinstance(norm, Normalize):
        return norm
    vals = vals[np.isfinite(vals)]
    if norm == "log":
        pos = vals[vals > 0]
        lo = float(lo_floor) if lo_floor else (float(pos.min()) if len(pos) else 1.0)
        hi = float(vmax or (pos.max() if len(pos) else lo * 10))
        return LogNorm(lo, max(hi, lo * 1.0001))
    if norm == "linear":
        return Normalize(0, float(vmax or (vals.max() if len(vals) and vals.max() > 0 else 1)))
    raise ValueError("norm 只能是 'log'、'linear' 或 Normalize 对象")


# ── 六边形热力 ────────────────────────────────────────────────────────────
def hexbin(geo, ax, df, size_m=None, *, lng="lng", lat="lat", value=None, how="count", min_value=5,
           small="blank", norm="log", vmax=None, cmap=None, clip=True, origin=None, n=40,
           edgecolor="white", lw=0.2, zorder=1.2, **kw) -> PolyCollection:
    if small not in ("blank", "gray"):
        raise ValueError(f"small 只能是 'blank'（不画）或 'gray'（浅灰），拿到 {small!r}")
    rings = _all_rings(geo)
    if clip and len(df):
        uc = df[[lng, lat]].drop_duplicates()
        keep = uc[_inside_any(rings, uc.to_numpy(float))]
        if len(keep) < len(uc):
            df = df.merge(keep, on=[lng, lat], how="inner")
    x0, y0, x1, y1 = geo.bounds
    lat0 = geo.lat0
    if size_m is None:
        size_m = nice_size((x1 - x0) * geo._k * M_PER_DEG, n)
    origin = origin or (round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1))
    cells = hexgrid(df, size_m, lng=lng, lat=lat, value=value, how=how, min_value=min_value, origin=origin, lat0=lat0)
    sup = cells["suppressed"].astype(bool).to_numpy()

    def verts(c):
        v = _hex_verts(*_to_m(c["lng"], c["lat"], origin, lat0), size_m)
        return np.stack(_to_deg(v[..., 0], v[..., 1], origin, lat0), axis=-1) if len(c) else np.empty((0, 6, 2))

    clip_patch = PathPatch(_union_path(rings), transform=ax.transData) if clip else None
    if small == "gray" and sup.any():
        pg = PolyCollection(verts(cells[sup]), facecolor=MC.small, edgecolor=edgecolor, linewidths=lw, zorder=zorder)
        ax.add_collection(pg, autolim=False)
        if clip_patch is not None:
            pg.set_clip_path(clip_patch)
    shown = cells[~sup]
    vals = shown["value"].to_numpy(float)
    pc = PolyCollection(verts(shown), array=vals, cmap=cmap or heat_cmap(),
                        norm=_make_norm(norm, vals, min_value, vmax),
                        edgecolor=edgecolor, linewidths=lw, zorder=zorder, **kw)
    ax.add_collection(pc, autolim=False)
    if clip_patch is not None:
        pc.set_clip_path(clip_patch)
    pc.cells, pc.size_m = cells, size_m
    return pc


# ── 色条：标实际数值，不标 10¹、10² ──────────────────────────────────────────
def _log_ticks(lo: float, hi: float, max_n: int = 7) -> list[float]:
    """1-3-10 序列落在 [lo, hi] 里的数，外加下限（通常是门槛 5）。太多就隔一个取一个，留首尾。"""
    t = [m * 10.0 ** e for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1)
         for m in (1, 3) if lo <= m * 10.0 ** e <= hi * 1.0001]
    if (not t or t[0] > lo * 1.0001) and float(f"{lo:.1g}") == lo:   # 下限是"整"数（门槛 5、20）才标；156 这种不标
        t = [lo, *[x for x in t if x >= lo * 1.6]]           # 下限和下一个刻度太近就让一个
    if not t:
        t = [lo, hi]
    while len(t) > max_n:
        t = t[::2] if len(t) % 2 else [*t[:-1:2], t[-1]]
    return t


def colorbar(mappable, ax, *, label: str, orientation: str = "horizontal", ticks: Iterable[float] | None = None,
             fmt: str = "{:,.0f}", shrink: float = 0.62, aspect: float = 32, pad: float = 0.015, **kw):
    """按规范出色条：对数色阶标 5、10、30、100…（千分位），无边框、无短刻度线。
    mappable：hexbin / fill 的返回值都行。ax：色条挂在哪个（或哪几个）ax 下面。返回 Colorbar。"""
    fig = (ax[0] if isinstance(ax, (list, tuple, np.ndarray)) else ax).figure
    cb = fig.colorbar(mappable, ax=ax, orientation=orientation, shrink=shrink, aspect=aspect, pad=pad, **kw)
    if ticks is None and isinstance(mappable.norm, LogNorm):
        ticks = _log_ticks(mappable.norm.vmin, mappable.norm.vmax)
    axis = cb.ax.xaxis if orientation == "horizontal" else cb.ax.yaxis
    if ticks is not None:
        axis.set_major_locator(FixedLocator(list(ticks)))
    axis.set_major_formatter(FuncFormatter(lambda v, _: fmt.format(v)))
    axis.set_minor_locator(NullLocator())
    cb.ax.tick_params(labelsize=9, length=0)
    cb.outline.set_visible(False)
    cb.set_label(label, fontsize=9.5, color=MC.ink)
    return cb


# ── 气泡：面积 ∝ 数值 ─────────────────────────────────────────────────────
def _ref_values(vmax: float, n: int = 3) -> list[float]:
    """图例参考值：1 / 2 / 5 × 10ⁿ 里不超过 vmax 的最大 n 个。"""
    c = sorted(m * 10.0 ** e for e in range(0, math.ceil(math.log10(max(vmax, 1))) + 1) for m in (1, 2, 5))
    return [v for v in c if v <= vmax][-n:]


def bubbles(geo, ax, df, value, *, lng="lng", lat="lat", hot=None, color=None, hot_color=None, smax=1600.0,
            vmax=None, min_value=5, alpha=0.78, legend: Mapping | bool = True, ref=None, title=None,
            zorder=3, **kw):
    v = pd.to_numeric(df[value], errors="coerce")
    keep = v >= (min_value if min_value is not None else -np.inf)
    hot_mask = np.zeros(len(df), bool) if hot is None else np.asarray(hot, bool)
    if len(hot_mask) != len(df):
        raise ValueError("hot 要和 df 一样长（布尔数组 / Series），标出要强调的那几行")
    d = df[keep.to_numpy()].assign(_v=v[keep], _hot=hot_mask[keep.to_numpy()])
    vmax = float(vmax or (d["_v"].max() if len(d) else 1))
    size = lambda u: np.asarray(u, float) / vmax * smax
    d = d.sort_values("_v", ascending=False)                    # 大的先画，小气泡压在上面不被盖住
    base, hc = color or MC.high, hot_color or MC.hot
    sc = ax.scatter(d[lng], d[lat], s=size(d["_v"]), c=np.where(d["_hot"], hc, base), alpha=alpha,
                    edgecolors="white", linewidths=0.8, zorder=zorder, **kw)
    sc.size_of = size                                           # 气泡面积（磅²）= size_of(数值)：自己标注时算半径用
    sc.data = d.drop(columns=["_hot", "_v"])                     # 画了的那些行，按数值从大到小
    sc.legend_ = None
    if legend is not False and len(d):
        ref = list(ref) if ref is not None else _ref_values(vmax)
        big = math.sqrt(size(max(ref)))
        opts = dict(loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=len(ref), frameon=False, fontsize=9,
                    title_fontsize=9.5, columnspacing=2.0, handletextpad=0.6, borderpad=0.2,
                    handleheight=big / 9 + 0.6, handlelength=big / 9 + 0.4)
        opts.update({} if legend is True else dict(legend))
        handles = [Line2D([], [], ls="", marker="o", ms=math.sqrt(size(r)), mfc=base, mec="white", alpha=alpha)
                   for r in ref]
        lg = ax.legend(handles, [f"{r:,.0f}" for r in ref], title=title or f"气泡面积 = {value}", **opts)
        lg.set_gid(FURNITURE)
        sc.legend_ = lg
    return sc


# ── 流向（OD）────────────────────────────────────────────────────────────
def _od_frame(od, origin, dest, value) -> pd.DataFrame:
    if isinstance(od, Mapping):
        od = pd.DataFrame([(o, d, v) for (o, d), v in od.items()], columns=[origin, dest, value])
    out = od[[origin, dest, value]].copy()
    out.columns = ["o", "d", "v"]
    out["o"], out["d"] = out["o"].astype(str), out["d"].astype(str)
    out["v"] = pd.to_numeric(out["v"], errors="coerce")
    return out.dropna(subset=["v"])


def flows(geo, ax, od, *, origin="o", dest="d", value="v", top=15, min_value=5, hot=3, at=None, bend=0.25,
          max_lw=8.0, min_lw=0.6, color=None, hot_color=None, fmt="{:,.0f}", labels=True,
          legend: Mapping | bool = True, unit="人", alpha=0.85, zorder=4):
    at = {str(k): np.asarray(v, float) for k, v in (at or {}).items()}
    t = _od_frame(od, origin, dest, value)
    report = dict(self_loops=int((t["o"] == t["d"]).sum()), small=0, unknown=[], beyond_top=0)
    t = t[t["o"] != t["d"]]
    known = set(geo.names) | set(at)
    if unk := sorted((set(t["o"]) | set(t["d"])) - known):
        warnings.warn(f"这些起讫点既不在边界里、也没在 at 里给坐标，没画：{unk}", stacklevel=3)
        report["unknown"] = unk
    t = t[t["o"].isin(known) & t["d"].isin(known)]
    if min_value is not None:
        report["small"] = int((t["v"] < min_value).sum())
        t = t[t["v"] >= min_value]
    t = t.sort_values("v", ascending=False, ignore_index=True)
    if top is not None and len(t) > top:
        report["beyond_top"] = len(t) - top
        t = t.head(top)
    t["hot"] = t.index < (hot or 0)
    pos = lambda n: at[n] if n in at else geo.anchor(n)
    vmax = float(t["v"].max()) if len(t) else 1.0
    width = lambda v: np.maximum(min_lw, np.asarray(v, float) / vmax * max_lw)     # 线宽 ∝ 数值（线宽就是长度量，线性比）
    base, hc, k = color or MC.high, hot_color or MC.hot, geo._k
    arrows, texts = {}, {}
    for row in t.iloc[::-1].itertuples():                       # 小的先画，大的压在上面
        p, q = pos(row.o), pos(row.d)
        w = float(width(row.v))
        c = hc if row.hot else base
        # 填充的箭头（不描边）：箭身宽 = w 磅，箭头按箭身放大。描边式箭头线越粗、箭头描边也越粗，会胀成一大块
        a = FancyArrowPatch(p, q, connectionstyle=f"arc3,rad={bend}", shrinkA=4, shrinkB=5, mutation_scale=1,
                            arrowstyle=f"simple,tail_width={w:.2f},head_width={1.8 * w + 4:.2f},head_length={1.2 * w + 5:.2f}",
                            fc=c, ec="none", lw=0, alpha=alpha, zorder=zorder + (0.5 if row.hot else 0))
        a.width = w
        ax.add_patch(a)
        arrows[(row.o, row.d)] = a
        if labels and row.hot:
            # arc3 曲线的中点 = 两端中点 + 0.5·rad·(dy, −dx)（显示坐标）；地图长宽比校正过，按米算等价
            # 数值写在弧线外凸那一侧、离开线身半个线宽 + 6 磅：短弧线也不会被数字盖住
            (px, py), (qx, qy) = (p[0] * k, p[1]), (q[0] * k, q[1])
            nx, ny = qy - py, -(qx - px)
            mx, my = (px + qx) / 2 + 0.5 * bend * nx, (py + qy) / 2 + 0.5 * bend * ny
            L = math.hypot(nx, ny) or 1.0
            ux, uy = (nx / L, ny / L) if bend >= 0 else (-nx / L, -ny / L)
            off = w / 2 + 6
            texts[(row.o, row.d)] = ax.annotate(
                fmt.format(row.v), (mx / k, my), xytext=(ux * off, uy * off), textcoords="offset points",
                ha="left" if ux > 0.3 else "right" if ux < -0.3 else "center",
                va="bottom" if uy > 0.3 else "top" if uy < -0.3 else "center",
                fontsize=9, color=hc, fontweight="bold", path_effects=HALO, zorder=zorder + 1)
    lg = None
    if legend is not False and len(t):
        ref = _ref_values(vmax)
        handles = [Line2D([], [], color=base, lw=float(width(r)), alpha=alpha) for r in ref]
        opts = dict(loc="upper left", frameon=False, fontsize=9, title_fontsize=9.5, handlelength=2.6)
        opts.update({} if legend is True else dict(legend))
        lg = ax.legend(handles, [f"{r:,.0f} {unit}" for r in ref], title="线宽 = 流量", **opts)
        lg.set_gid(FURNITURE)
    return SimpleNamespace(arrows=arrows, texts=texts, data=t.rename(columns={"o": origin, "d": dest, "v": value}),
                           legend=lg, dropped=report)


# ── 小多图：同一底图、同一色阶 ─────────────────────────────────────────────
def facets(geo, data, *, ncols=None, norm="linear", vmax=None, cmap=None, height=3.0, label="", text=False,
           fmt="{:,.0f}", hot_max=True, land=True, titles: Mapping | None = None, min_value=None, small="hatch",
           **fill_kw):
    if isinstance(data, pd.DataFrame):
        panels = {str(c): data[c] for c in data.columns}
    else:
        panels = {str(k): v for k, v in dict(data).items()}
    if not panels:
        raise ValueError("data 是空的：给 {面板名: {区名: 数值}}，或行 = 区、列 = 面板的 DataFrame")
    n = len(panels)
    ncols = ncols or min(n, 4)
    nrows = math.ceil(n / ncols)
    allv = np.array([float(x) for v in panels.values() for x in pd.Series(v).to_numpy(dtype=float)], float)
    if min_value is not None:
        allv = allv[~(allv < min_value)]                       # 被藏的数不参与定色阶
    nm = _make_norm(norm, allv, None, vmax) if not isinstance(norm, Normalize) else norm
    if not isinstance(norm, Normalize) and norm == "log":
        nm = LogNorm(nm.vmin * 0.6, nm.vmax)                    # 和 fill 一样留一点底色：最小值不是纯白
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * height * geo.aspect + 0.3, nrows * height + 0.9),
                             layout="constrained", squeeze=False)
    flat = axes.ravel()
    pcs = []
    for i, (name, vals) in enumerate(panels.items()):
        ax = flat[i]
        geo.base(ax, land=land, scale=i == 0, north=i == 0, fill=False)
        with warnings.catch_warnings():                        # "只剩一个区被藏"的提醒每张面板都会响，小多图里只提醒一次
            warnings.simplefilter("ignore" if i else "default")
            pc = geo.fill(ax, vals, norm=nm, cmap=cmap, min_value=min_value, small=small, **fill_kw)
        pcs.append(pc)
        ax.set_title((titles or {}).get(name, name), loc="left", fontsize=10.5, color=MC.ink)
        s = pd.Series(vals, dtype=float).dropna()
        if min_value is not None:
            s = s[~(s < min_value)]                             # "最多的区"不会是被藏的区
        if hot_max and len(s):
            geo.edges(ax, [s.idxmax()], lw=1.4)                 # 每张面板最大的区：整圈描边（数字放不下时也看得出）
        if text and len(pd.Series(vals, dtype=float).dropna()):
            geo.text(ax, pd.Series(vals, dtype=float).dropna(), fmt=fmt, overflow="hide",
                     hot=[s.idxmax()] if hot_max else (), min_value=min_value)
    for ax in flat[n:]:
        ax.set_axis_off()
    cb = colorbar(pcs[0], list(flat[:n]), label=label, shrink=min(0.6, 0.25 * ncols))
    return fig, axes, cb


# ── 放大图配件 ────────────────────────────────────────────────────────────
def circle(ax, lng: float, lat: float, radius_m: float, *, lat0: float | None = None, **kw) -> Ellipse:
    """按米画圆：经纬度上是椭圆，配长宽比校正画出来是正圆。默认 colors.hot 虚线、不填充；fc=... 加底色。"""
    rx, ry = m2deg(radius_m, lat if lat0 is None else lat0)
    style = dict(fc="none", ec=MC.hot, lw=1.3, ls=(0, (5, 3)), zorder=2.5)
    e = Ellipse((lng, lat), 2 * rx, 2 * ry, **{**style, **kw})
    ax.add_patch(e)
    return e


def zoom(src, dst, lng: float, lat: float, half_m, *, label: str | None = None, color: str | None = None,
         connect: bool = False, lat0: float | None = None) -> SimpleNamespace:
    """src 上画放大框（白边：压在深色热力上也看得见），dst 设成框里的范围：视窗、长宽比、同色边框。

    half_m:  框的半宽（米）；(半宽, 半高) 做长方形。
    label:   写在框左上方（colors.hot 加粗）。同色 + 同名，读者就能把框和放大图对上，一般不用连接线。
    connect: True 从框的两角连线到 dst 的两角，线画在所有 axes 上面（白描边），会横穿 src——框很小、离 dst 很远时再开。
    dst 可以先 geo.base(dst, fill=False) 画底色和区界，再 zoom；dst 上已有的比例尺、指北针会按新视窗重放。
    返回 SimpleNamespace(rect, text, lines, extent=(x0, x1, y0, y1))。
    """
    color = color or MC.hot
    lat0 = lat if lat0 is None else lat0
    hw, hh = (half_m, half_m) if np.isscalar(half_m) else half_m
    dx, _ = m2deg(hw, lat0)
    _, dy = m2deg(hh, lat0)
    x0, x1, y0, y1 = lng - dx, lng + dx, lat - dy, lat + dy

    if getattr(dst, "_viz_fit_installed", False):              # frame(fill=True) 会把视窗撑满 ax：放大图要的是框里这块
        del dst.apply_aspect
        dst._viz_fit_installed = False
    dst.set_xlim(x0, x1)
    dst.set_ylim(y0, y1)
    dst.set_aspect(1 / math.cos(math.radians(lat0)), adjustable="box")
    dst.set_xticks([]); dst.set_yticks([]); dst.grid(False)
    if hasattr(dst, "_viz_frame"):
        dst._viz_frame = (x0, x1, y0, y1, 1 / math.cos(math.radians(lat0)))
        dst._viz_last = (x0, x1, y0, y1)
    for sp in dst.spines.values():
        sp.set_visible(True); sp.set_color(color); sp.set_linewidth(1.4)
    from . import maps                                          # 运行时取：maps import 本模块
    kinds = {getattr(a, "_viz_kind", None) for a in [*dst.lines, *dst.texts]}
    if "scale" in kinds:
        maps.scale_bar(dst, lat0=lat0)
    if "north" in kinds:
        maps.north_arrow(dst)

    rect = Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=color, lw=1.4, zorder=5,
                     path_effects=[pe.withStroke(linewidth=3.4, foreground="white")])
    src.add_patch(rect)
    text = None
    if label:
        text = src.text(x0, y1 + dy * 0.25, label, ha="left", va="bottom", fontsize=10, color=color,
                        fontweight="bold", path_effects=HALO, zorder=5)
    lines = []
    if connect:
        right = dst.get_position().x0 >= src.get_position().x1 - 1e-6    # dst 在右边就连框的右侧两角
        pairs = ([((x1, y1), (0, 1)), ((x1, y0), (0, 0))] if right else [((x0, y1), (1, 1)), ((x0, y0), (1, 0))])
        for a, b in pairs:
            cp = ConnectionPatch(a, b, "data", "axes fraction", axesA=src, axesB=dst, color=color, lw=0.8,
                                 alpha=0.8, zorder=10, path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])
            src.figure.add_artist(cp)
            lines.append(cp)
    return SimpleNamespace(rect=rect, text=text, lines=lines, extent=(x0, x1, y0, y1))


def locator(geo, ax, highlight: Iterable[str] = (), *, box=None, loc: str = "lower right", width: float = 0.28,
            pad: float = 0.02):
    hi = set(map(str, highlight))
    geo._known(hi, "highlight")
    hgt = width / geo.aspect * (ax.bbox.width / max(ax.bbox.height, 1))
    bx = pad if "left" in loc else 1 - pad - width
    by = pad if "lower" in loc else 1 - pad - hgt
    ins = ax.inset_axes([bx, by, width, hgt], zorder=6)
    geo.frame(ins, margin=0.04, fill=False)
    ins.set_anchor(("S" if "lower" in loc else "N") + ("W" if "left" in loc else "E"))
    ins.set_facecolor("white")
    for sp in ins.spines.values():
        sp.set_visible(True); sp.set_color(MC.line); sp.set_linewidth(0.5)
    rest = [PathPatch(p) for n, p in geo._paths.items() if n not in hi]
    mark = [PathPatch(p) for n, p in geo._paths.items() if n in hi]
    ins.add_collection(PatchCollection(rest, fc=MC.land, ec="white", lw=0.4), autolim=False)
    ins.add_collection(PatchCollection(mark, fc=MC.heat_mid, ec="white", lw=0.4), autolim=False)
    if box is not None:
        bx0, by0, bx1, by1 = box
        ins.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=False, ec=MC.hot, lw=1.0, zorder=5))
    return ins
