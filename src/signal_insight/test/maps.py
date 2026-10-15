#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : maps.py
# @Path       : signal-insight/src/signal_insight/test/maps.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-14 11:12:09
# @Version    : v1.0.0
# @Description: 
# @ChangeLog:
#   2026-10-14 11:12:09 | Matri | v1.0.0 | 初始化创建
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : maps.py
# @Path       : signal-insight/src/signal_insight/viz/maps.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-14 08:36:03
# @Version    : v1.1.0
# @Description:
# @ChangeLog:
#   2026-10-14 08:36:03 | Matri | v1.0.0 | 初始化创建
#   2026-10-14       | Matri | v1.1.0 | draw 拆成可组合原语；新增 colorize；标注改保序堆叠
"""地图：长宽比校正、比例尺、指北针，以及区县专题图 DistrictMap。

和 theme.py 分开，是因为改动原因不同（AGENTS.md 第 2 条）：改配色的人不该面对一堆地图代码；
地图要按纬度换算距离、算标注位置，主题不需要。
不读数据库：多边形由调用方用 geo.rings_from_points 还原好传进来（AGENTS.md 第 4 条）。

用法分三层，按需选用：
  1. 只有经纬度底图：set_map_aspect、scale_bar、north_arrow 三个函数；
  2. 全市区县专题图，一键默认：::

        dm = viz.maps.DistrictMap(districts)              # {区县名: [环, ...]}
        fig, ax, gs = dm.figure(cols=[0.35, 4.2], n_sub=2)
        dm.draw(ax, values, texts, hot=["辽中区"], norm="log",
                dots=[(sites, viz.INK)])
        viz.finish(fig, title, subtitle, SOURCE, "D3_xx_xxx.png")

  3. 需要插入自己的东西：用原语自己组合，顺序随意：:

        cmap, norm = viz.maps.colorize(values, norm="log")
        dm.fill(ax, {n: cmap(norm(v)) for n, v in values.items()})
        dm.dots(ax, sites, viz.INK)
        dm.outline(ax)
        ax.plot(...)                                      # 你想画什么画什么
        dm.labels(ax, texts, hot=["辽中区"])
        dm.decorate(ax, km=20)
"""
from __future__ import annotations

import warnings
from typing import Iterable, Mapping

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize
from matplotlib.path import Path

from .theme import GRAY_DARK, INK, MAIN, MUTED, margins_in   # theme 不 import maps

__all__ = [
    "LAT0", "set_map_aspect", "scale_bar", "north_arrow",
    "colorize", "DistrictMap",
]

LAT0 = 41.8      # 沈阳大约的纬度：经度 1 度的长度只有纬度 1 度的 cos(41.8°) ≈ 0.75 倍
_CMAP_DEFAULT = LinearSegmentedColormap.from_list("district", ["white", GRAY_DARK])

# 引线留白：给指北针（上）和比例尺（下）各留一块，单位是视窗高度比例
_TOP_RESERVE = 0.20
_BOT_RESERVE = 0.14


# ============================================================== 底图工具
def set_map_aspect(ax, lat0: float = LAT0, bare: bool = True) -> None:
    """长宽比校正：经纬度不能直接当平面坐标画，否则东西方向被拉宽约 1/0.75 倍。
    bare=True 时去掉刻度、网格和边框：读者用不到经纬度刻度，比例尺才有用。"""
    ax.set_aspect(1 / np.cos(np.radians(lat0)), adjustable="box")
    if bare:
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)


def scale_bar(ax, km: float, lat0: float = LAT0) -> None:
    """左下角比例尺：按纬度把公里换成经度差。先设好 xlim、ylim 再调用（位置按当前视窗算）。"""
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    deg = km / (111.32 * np.cos(np.radians(lat0)))
    xs, ys = x0 + 0.04 * (x1 - x0), y0 + 0.04 * (y1 - y0)
    ax.plot([xs, xs + deg], [ys, ys], color=INK, lw=1.2, solid_capstyle="butt")
    for x in (xs, xs + deg):                                         # 两端短竖线
        ax.plot([x, x], [ys, ys + 0.008 * (y1 - y0)], color=INK, lw=0.8)
    ax.text(xs + deg / 2, ys + 0.018 * (y1 - y0), f"{km:g} 公里",
            ha="center", va="bottom", fontsize=9, color=INK)


def north_arrow(ax, x: float = 0.95, y: float = 0.95) -> None:
    """指北针（坐标是轴内比例，默认右上角）。"""
    ax.annotate("北", xy=(x, y), xytext=(x, y - 0.08), xycoords="axes fraction",
                ha="center", va="top", fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.8, shrinkA=0, shrinkB=0))


# ============================================================== 色阶
def colorize(values: Mapping[str, float] | Iterable[float],
             cmap=None, norm: str | Normalize = "linear"):
    """把数值映射成色阶。返回 (cmap, norm)，供调用方自己算颜色。

    norm  "linear"（0 → 最大值）| "log"（对数，数值差一个数量级以上）| 自传 Normalize 对象。
    内部会处理全相等、含零、含 NaN 这些边角；调用方不必操心。"""
    cmap = cmap or _CMAP_DEFAULT
    if not isinstance(norm, str):
        return cmap, norm
    v = np.asarray(list(values.values()) if isinstance(values, Mapping) else list(values),
                   dtype=float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return cmap, Normalize(0, 1)
    vmin, vmax = float(v.min()), float(v.max())
    if norm == "log":
        if vmin <= 0:
            pos = v[v > 0]
            vmin = float(pos.min()) if len(pos) else 1e-9
        if vmin >= vmax:
            vmax = vmin * 10                                # 全相等时给一个跨度，别退化成奇异
        return cmap, LogNorm(vmin * 0.6, vmax)              # 留一点底色，最小值不会纯白
    if norm == "linear":
        if vmin >= vmax:
            vmax = vmin + 1
        return cmap, Normalize(0, vmax)
    raise ValueError("norm 只能是 'linear'、'log' 或 Normalize 对象")


# ============================================================== 几何小工具
def _pole_point(rings: list[np.ndarray], lat0: float) -> np.ndarray:
    """落点：区内离边界最远的点。一定落在区里、不贴边，引线进区的位置比“离中心最近”稳。"""
    r = max(rings, key=len)
    lo, hi = r.min(0), r.max(0)
    gx, gy = np.meshgrid(np.linspace(lo[0], hi[0], 45), np.linspace(lo[1], hi[1], 45))
    g = np.column_stack([gx.ravel(), gy.ravel()])
    g = g[Path(r).contains_points(g)]
    if len(g) == 0:
        return r.mean(axis=0)
    edge = np.vstack([np.linspace(r[i], r[(i + 1) % len(r)], 6, endpoint=False) for i in range(len(r))])
    edge = edge[:: max(1, len(edge) // 400)]
    k = [np.cos(np.radians(lat0)), 1]                                  # 经度差按纬度折成同一长度
    dist = np.sqrt((((g[:, None, :] - edge[None, :, :]) * k) ** 2).sum(-1)).min(1)
    return g[dist.argmax()]


def _stack(order, targets, lo: float, hi: float, gap: float) -> dict:
    """保序堆叠：把 targets 压进 [lo, hi]，间距不小于 gap，尽量贴近原值。

    order  已经按北 → 南排好（y 递减）的名字
    targets 对应的锚点 y
    返回 {name: y}。全部是 O(n)，不迭代、不交换；标签从上到下对应地图上从北到南，读者能预期。"""
    n = len(order)
    if n == 0:
        return {}
    if (n - 1) * gap >= hi - lo:                        # 太挤就等距展开，行距自动压缩
        return dict(zip(order, np.linspace(hi, lo, n)))
    ys = list(np.clip(targets, lo, hi))
    for i in range(1, n):                               # 前向：压最小间距
        ys[i] = min(ys[i], ys[i - 1] - gap)
    if ys[-1] < lo:                                     # 后向：整体上移
        shift = lo - ys[-1]
        ys = [y + shift for y in ys]
        if ys[0] > hi:                                  # 还是不行就等距
            return dict(zip(order, np.linspace(hi, lo, n)))
    return dict(zip(order, ys))


# ============================================================== DistrictMap
class DistrictMap:
    """一份区县边界对应一个 DistrictMap。边界相同，视窗、落点、标注位置就相同。

    几个尺寸（类属性，改了会影响所有用它画的图；想只改一张图就在构造时传参）：
    map_h_in   地图高度（英寸）。想放大地图改这个，宽度会按长宽比自动反推。
    label_w_in 标注文字预留宽度（英寸）。
    head_in    右侧各列标题所在行的高度（英寸）。
    elbow, stub, txt_gap  单位是度：拐点离地图外缘、等长短横线、文字离短横线。
    """

    map_h_in, label_w_in, head_in = 7.0, 1.30, 0.50
    elbow, stub, txt_gap = 0.07, 0.14, 0.02

    def __init__(self, districts: Mapping[str, Iterable], lat0: float = LAT0, **sizes: float):
        for k, v in sizes.items():
            if k not in ("map_h_in", "label_w_in", "head_in", "elbow", "stub", "txt_gap"):
                raise TypeError(f"未知参数：{k}")
            setattr(self, k, v)
        self.lat0 = lat0
        self.polys = {n: [np.asarray(r, float) for r in rings] for n, rings in districts.items()}
        pts = np.vstack([r for rings in self.polys.values() for r in rings])
        (self.bx0, self.by0), (self.bx1, self.by1) = pts.min(0), pts.max(0)

        # 版面：由地图外框反推子图的纵向范围、宽度（英寸）、横向范围
        self.ylim = (self.by0 - 0.03, self.by1 + 0.03)                  # 上下各留 0.03°
        dy = (self.ylim[1] - self.ylim[0]) / self.map_h_in              # 每英寸多少纬度
        dx = dy / np.cos(np.radians(lat0))                              # 每英寸多少经度
        side_in = (self.elbow + self.stub + self.txt_gap) / dx + self.label_w_in + 0.05
        self.left_w_in = (self.bx1 - self.bx0) / dx + 2 * side_in
        xc = (self.bx0 + self.bx1) / 2
        self.xlim = (xc - self.left_w_in / 2 * dx, xc + self.left_w_in / 2 * dx)

        self.anchors = {n: _pole_point(rings, lat0) for n, rings in self.polys.items()}

    # ------------------------------------------------------------------ 版面
    def figure(self, cols: Iterable[float] = (), n_sub: int = 2):
        """建图：左边是地图，右边按 cols（英寸）留出列。返回 (fig, 地图轴, gs)。
        gs 是 2 行 × (1+len(cols)) 列：第 0 列是地图（跨两行），第 1 行是右侧画图的区域，第 0 行留给列标题。
        cols 里不想放图的列（比如列与列之间的空隙）就不要往里面画。
        n_sub 是 viz.finish 里副标题的行数，用来留够标题区，这样不同图里的地图一样大。"""
        cols = list(cols)
        fig_w = 0.3 + self.left_w_in + sum(cols) + 0.2
        head, foot = margins_in(n_sub)                                  # 与 finish() 同一处留白数字
        fig_h = self.map_h_in + head + foot + 0.25
        fig = plt.figure(figsize=(fig_w, fig_h))
        gs = fig.add_gridspec(2, 1 + len(cols), hspace=0, wspace=0,
                    height_ratios=[self.head_in, self.map_h_in - self.head_in],
                    width_ratios=[self.left_w_in, *cols])
        return fig, fig.add_subplot(gs[:, 0]), gs

    def clip(self, df: pd.DataFrame, pad: float = 0.15, lng: str = "lng", lat: str = "lat") -> pd.DataFrame:
        """只留地图视窗内的点：边界外扩 pad 度（默认 0.15°，市外的点画一圈），上下用地图上下沿。"""
        return df[df[lng].between(self.bx0 - pad, self.bx1 + pad) & df[lat].between(*self.ylim)]

    # ------------------------------------------------------------------ 原语
    def setup(self, ax) -> None:
        """把坐标轴设成地图视窗：xlim/ylim/长宽比/去刻度。想自己画整张图可以先调它。"""
        ax.set_xlim(*self.xlim)
        ax.set_ylim(*self.ylim)
        set_map_aspect(ax, self.lat0)

    def fill(self, ax, colors: Mapping[str, str] | None = None) -> None:
        """按 {区县名: 颜色} 填色。颜色可以是任何 matplotlib 认的东西（含 "none"）。
        没给到的区县不填。色阶用 colorize() 自己算好再传进来，这里只认颜色。"""
        colors = colors or {}
        for name, rings in self.polys.items():
            fc = colors.get(name, "none")
            if fc == "none":
                continue
            for r in rings:
                ax.fill(r[:, 0], r[:, 1], facecolor=fc, edgecolor="white", lw=0.9)

    def outline(self, ax, lw: float = 0.9) -> None:
        """全市外缘：只出现一次的边就是外缘（两个区共用的边出现两次，不画），画一圈深色细线。
        若相邻两区共用边的顶点坐标对不上，区与区之间也会被画上深色线，这时说明边界数据不是拓扑一致的。"""
        seen, segs = {}, []
        for rings in self.polys.values():
            for r in rings:
                for p, q in zip(r, np.roll(r, -1, axis=0)):
                    if np.allclose(p, q):
                        continue
                    key = frozenset((tuple(np.round(p, 5)), tuple(np.round(q, 5))))
                    seen[key] = seen.get(key, 0) + 1
                    segs.append((key, (p, q)))
        ax.add_collection(LineCollection([sg for k, sg in segs if seen[k] == 1],
                                         colors=INK, linewidths=lw, capstyle="round", zorder=3))

    def dots(self, ax, df: pd.DataFrame, color: str = INK, s: float = 1.0,
             zorder: int = 3, lng: str = "lng", lat: str = "lat") -> None:
        """在地图上打点。df 需有 lng/lat 两列。可以调多次叠不同颜色/大小的层。"""
        ax.scatter(df[lng], df[lat], s=s, color=color, lw=0, zorder=zorder)

    def labels(self, ax, texts: Mapping[str, str], *, hot: Iterable[str] = (),
               fs: float = 9) -> None:
        """左右两列上下等距标注。引线 = 等长短横线 → 拐点 → 直线进区。

        分侧：落点按经度排序，西边一半在左列、东边一半在右列。
        拐点：贴着地图外缘，同一列在同一条竖线上，所以进区的斜线从同一处散开。
        行位：两列共用同一个上下范围；用保序堆叠（_stack）确保不重叠、不交叉。
        hot 里的区县用 MAIN 色加粗。"""
        if not texts:
            return
        y0, y1 = self.ylim
        span = y1 - y0
        # 行距：按字号折算成度（fs 点 × 1.35 行高 ÷ 72 英寸/点 × 每英寸多少度）
        gap = fs * 1.35 / 72.0 * span / self.map_h_in
        lo = y0 + _BOT_RESERVE * span                         # 底下留给比例尺
        hi = y1 - _TOP_RESERVE * span                         # 上面留给指北针
        line = dict(color=MUTED, lw=0.45)                     # 引线：细、灰，不和区界抢

        by_x = sorted(texts, key=lambda n: self.anchors[n][0])
        half = (len(by_x) + 1) // 2
        for left, names in ((True, by_x[:half]), (False, by_x[half:])):
            ex = self.bx0 - self.elbow if left else self.bx1 + self.elbow    # 拐点
            tx = ex - self.stub if left else ex + self.stub                  # 文字端
            order = sorted(names, key=lambda n: -self.anchors[n][1])         # 北 → 南
            targets = [self.anchors[n][1] for n in order]
            ys = _stack(order, targets, lo, hi, gap)
            for n in order:
                lng, lat = self.anchors[n]
                ax.plot([tx, ex, lng], [ys[n], ys[n], lat], zorder=5,
                        solid_joinstyle="round", **line)
                ax.plot(lng, lat, "o", ms=2.2, color=INK, mec="white", mew=0.4, zorder=6)
                ax.text(tx + (-self.txt_gap if left else self.txt_gap), ys[n], texts[n],
                        ha="right" if left else "left", va="center", fontsize=fs, zorder=6,
                        color=MAIN if n in hot else INK,
                        fontweight="bold" if n in hot else "normal")

    def decorate(self, ax, km: float = 20) -> None:
        """比例尺 + 指北针。要在 setup / draw 设好视窗之后调。"""
        scale_bar(ax, km, self.lat0)
        north_arrow(ax)

    # ------------------------------------------------------------------ 一键
    def draw(self, ax, values: Mapping[str, float] | pd.Series | None = None,
             texts: Mapping[str, str] | None = None, *, hot: Iterable[str] = (),
             norm: str | Normalize = "linear", cmap=None,
             dots: Iterable[tuple[pd.DataFrame, str]] = (),
             km: int = 20, fs: float = 9):
        """默认整图：setup → fill → outline → dots → labels → decorate。
        想插入自己的图层就改用原语（见模块 docstring）。

        values  {区县名: 数值}，按数值填色（白 → GRAY_DARK）；不给就不填色。
        texts   {区县名: 标注文字}，左右两列引线标注；不给就不标。
        hot     texts 里要强调的区县名：MAIN 色加粗。
        dots    [(DataFrame(lng, lat), 颜色), ...]，叠在填色上的点，先传的在下面。
        返回 (cmap, norm)；values 为空时返回 (None, None)。"""
        asked = list(values or {}) + list(texts or {})
        missing = [n for n in asked if n not in self.polys]
        if missing:
            warnings.warn(f"districts 里找不到这些区县，地图上不画：{sorted(set(missing))}")

        self.setup(ax)

        if values is not None:
            cmap, norm = colorize(values, cmap, norm)
            self.fill(ax, {n: cmap(norm(v)) for n, v in values.items()})
            out = (cmap, norm)
        else:
            out = (None, None)

        self.outline(ax)
        for item in dots:
            df, color = item[0], item[1]
            self.dots(ax, df, color)
        if texts:
            self.labels(ax, {n: t for n, t in texts.items() if n in self.polys},
                        hot=hot, fs=fs)
        self.decorate(ax, km=km)
        return out


if __name__ == '__main__':
    pass

if __name__ == '__main__':
    pass
