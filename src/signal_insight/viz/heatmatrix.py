#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : heatmatrix.py
# @Path       : signal-insight/src/signal_insight/viz/heatmatrix.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-16 10:00:00
# @Version    : v1.0.0
# @Description: 热力矩阵 viz.matrix：A 与 B 的关系（OD、联动、交叉表），格子里写数字，小样本自动抑制
# @ChangeLog:
#   2026-10-16 10:00:00 | Matri | v1.0.0 | 初始化创建

"""热力矩阵：规范第 4 节"矩阵（A 与 B 的关系）→ 热力矩阵，格子里写数字"。

最常见的三种用法::

    from signal_insight import viz

    # 1) 长表：一行一条记录（居住区, 工作区, 人数）→ 自动透视成矩阵
    m = viz.matrix(od, row="居住区", col="工作区", value="人数")

    # 2) 宽表：行 = A，列 = B，格子 = 数值（df.pivot 出来的样子）
    m = viz.matrix(wide)

    # 3) 看占比：每一行加起来 = 100%（"住在 X 的人，去哪些区上班"）
    m = viz.matrix(od, row="居住区", col="工作区", value="人数", percent="row")

    viz.finish(m.ax.figure, 标题, 副标题 + m.note, 来源, "D14_03_联动矩阵.png")

每个格子画什么，按下面的顺序判断（先命中先算）：

    数据里没有这一格（NaN）             → 白底，不写字
    对角线 diagonal="hide"               → 白底，不写字
    人数 < min_value（默认 5）           → 浅灰底，写 "<5"          （规范第 7 节：小样本不公布）
    互补抑制（见下）                     → 浅灰底，写 "*"
    对角线 diagonal="gray"               → 浅灰底，灰字写数值，不参与色阶
    其余                                 → 按数值上色（浅蓝 → 深蓝），写数值

互补抑制（为什么有 "*"）：
    如果图上写了合计（totals=True），或者按行算了占比（percent="row"，每行加起来是 100%），
    而某一行只有一个格子是 "<5"，读者用"合计 − 其余格子"就能把它算出来——等于没藏住。
    所以这种行要再藏一个格子（挑这一行里最小的那个），让这一行至少有两个格子看不见，
    两个未知数一个方程，就解不出来了。列也一样。被多藏的格子写 "*"，m.note 里有一句说明，抄进副标题即可。
    只有 totals / percent 会让读者"反推"，两者都不开时不做互补抑制。

返回 MatrixPlot：ax（画在哪）、counts（排好序的人数矩阵）、shown（每格实际写了什么）、
suppressed / secondary（哪些格子被藏、哪些是互补抑制）、texts（按 (行, 列) 取格子里的文字）、note（副标题说明）。
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize, to_rgb
from matplotlib.patches import Rectangle

from .theme import FAINT, GRAY, INK, MAIN, MAIN_DARK, MAIN_LIGHT, MAIN_MID, MUTED

__all__ = ["matrix", "MatrixPlot", "suppress_cells", "fmt_pct"]

SMALL_BG = "#EEF0F3"      # "<5" 和 "*" 格子的底色：比白深一点，一眼看出"这里有数，但不公布"
DIAG_BG = "#F5F6F8"       # diagonal="gray" 时对角线的底色


# ══ 数字的写法（规范第 6 节）════════════════════════════════════════════════
def fmt_pct(v: float) -> str:
    """百分比（v 是 0~1 的比例）：一般取整（40%）；不到 1% 保留一位（0.4%）；不到 0.1% 保留两位（0.04%）。
    规范第 6 节："很小的值自动多保留位数，不写 0.0%"。"""
    p = v * 100
    if p == 0:
        return "0%"
    if abs(p) < 0.1:
        return f"{p:.2f}%"
    if abs(p) < 1:
        return f"{p:.1f}%"
    return f"{p:.0f}%"


def _as_formatter(fmt) -> Callable[[float], str]:
    if callable(fmt):
        return fmt
    return lambda v: fmt.format(v)


# ══ 数据整理 ═══════════════════════════════════════════════════════════════
def _to_wide(data, row, col, value) -> pd.DataFrame:
    """长表 → 宽表（行 × 列），或者宽表原样复制。同一 (行, 列) 出现多次就相加。"""
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"data 要是 pandas DataFrame，拿到 {type(data).__name__}")
    given = [x is not None for x in (row, col, value)]
    if any(given) and not all(given):
        raise ValueError("长表要同时给 row=、col=、value= 三个列名（行、列、数值）；宽表三个都不给")
    if all(given):
        missing = [c for c in (row, col, value) if c not in data.columns]
        if missing:
            raise KeyError(f"data 里没有这些列：{missing}；现有的列：{list(data.columns)}")
        wide = data.pivot_table(index=row, columns=col, values=value, aggfunc="sum", observed=True)
        wide.index.name, wide.columns.name = row, col
    else:
        wide = data.copy()
    wide.index = wide.index.map(str)
    wide.columns = wide.columns.map(str)
    try:
        wide = wide.astype(float)
    except (TypeError, ValueError) as e:
        raise TypeError("矩阵里的值要都是数（人数）。长表请给 row/col/value 三个列名，让函数自己透视") from e
    return wide


def _is_square(wide: pd.DataFrame) -> bool:
    """行和列是同一组名字（OD 矩阵：从 A 区到 B 区）。这时才有"对角线"。"""
    return set(wide.index) == set(wide.columns)


def _apply_order(wide: pd.DataFrame, order, square: bool) -> pd.DataFrame:
    """order：None 按数据原样；"total" 按合计从大到小；列表 = 行的顺序（方阵时列也用同一顺序）；
    (行列表, 列列表) 分别指定。方阵里行、列始终同序，对角线才是一条斜线。"""
    if order is None:
        if square:                                          # 方阵：列跟着行的顺序走
            return wide.loc[:, list(wide.index)]
        return wide
    if isinstance(order, str):
        if order != "total":
            raise ValueError(f"order 只能是 None、'total'、列表，或 (行列表, 列列表)，拿到 {order!r}")
        if square:
            tot = wide.sum(axis=1).add(wide.sum(axis=0), fill_value=0).sort_values(ascending=False)
            rows = cols = list(tot.index)
        else:
            rows = list(wide.sum(axis=1).sort_values(ascending=False).index)
            cols = list(wide.sum(axis=0).sort_values(ascending=False).index)
        return wide.loc[rows, cols]
    if isinstance(order, tuple) and len(order) == 2:
        rows, cols = [str(x) for x in order[0]], [str(x) for x in order[1]]
    else:
        rows = [str(x) for x in order]
        cols = rows if square else list(wide.columns)
    for what, want, have in (("行", rows, wide.index), ("列", cols, wide.columns)):
        if bad := [x for x in want if x not in have]:
            raise KeyError(f"order 里这些{what}名在数据里没有：{bad}")
        if left := [x for x in have if x not in want]:
            warnings.warn(f"order 没列出这些{what}，它们不会画出来：{left}", stacklevel=4)
    return wide.loc[rows, cols]


# ══ 小样本抑制 ═════════════════════════════════════════════════════════════
def suppress_cells(counts: pd.DataFrame, min_value: float | None = 5, *, rows: bool = False, cols: bool = False,
                   hidden: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """算出哪些格子要藏。返回 (primary, secondary)，都是和 counts 同形状的布尔表。

    primary：   人数 < min_value 的格子（NaN 不算——NaN 是"没有这一格"，不是"人少"）。
    secondary： 互补抑制多藏的格子。rows=True 表示读者知道每行的合计（画了合计列、或按行算了占比），
                那么任何一行"看不见的格子"恰好 1 个、而且它是被藏的小数时，就在这一行里再藏一格；cols 同理。
                挑哪一格：先挑"所在列也正好缺一个"的（一格补两条线），没有就挑最小的。
                反复检查到行、列都满足"看不见的格子是 0 个或至少 2 个"为止。
                （藏得最少的方案一般很难算，这是常用的贪心做法：结果一定安全，个数接近最少。）
    hidden：    本来就不显示的格子（比如 diagonal="hide" 的对角线）。它们也算"看不见"，
                所以一行里有一个 <5 加一个隐藏的对角线，已经是两个未知数，不用再多藏。

    单独调用也行：自己做表格（Excel、Word）时，同样的规则先算一遍再填。
    """
    vals = counts.to_numpy(float)
    finite = np.isfinite(vals)
    primary = finite & (vals < min_value) if min_value is not None else np.zeros_like(finite)
    hide = np.zeros_like(finite) if hidden is None else hidden.to_numpy(bool)
    secondary = np.zeros_like(finite)
    unseen = lambda: primary | secondary | hide
    for _ in range(vals.size + 1):                          # 每轮至少多藏一格，最多 vals.size 轮
        changed = False
        for axis, on in ((1, rows), (0, cols)):
            if not on:
                continue
            u = unseen()
            prot = primary | secondary                       # 要保护的格子（小数，或已经为保护小数藏起来的）
            # 一条线"有危险" = 看不见的格子正好 1 个、而且它是要保护的格子。
            # 只藏了对角线（diagonal="hide"）的线不算：对角线是显示上的选择，它本身 ≥ 门槛，被算出来也没关系
            risky = lambda ax_: ((u & (finite | hide)).sum(axis=ax_) == 1) & ((prot & finite).sum(axis=ax_) >= 1)
            n_risky = risky(axis)
            perp_on = cols if axis == 1 else rows
            other = risky(1 - axis) & perp_on                # 垂直方向上也"有危险"的线
            this_risky = n_risky.copy()
            for i in np.nonzero(n_risky)[0]:
                line_vals = vals[i] if axis == 1 else vals[:, i]
                cand = (finite & ~u)[i] if axis == 1 else (finite & ~u)[:, i]
                if not cand.any():
                    continue                                 # 这一行只剩它自己：合计就等于它，合计本身也会 <5 被藏
                # 挑哪一格，分三档（同档挑数最小的，藏小数对读者损失最小）：
                #   0 档：所在列也"有危险"，而且那一列唯一看不见的格子所在的行也还没修好——
                #         藏这一格补好一行一列，还把链条接到另一条没修好的行上，最后能连成一个环；
                #   1 档：所在列也"有危险"（藏一格补两条线，但可能提前闭环）；
                #   2 档：其余格子。
                tier = np.full(len(line_vals), 2.0)
                for j in np.nonzero(cand & other)[0]:
                    line = (u & (finite | hide))[:, j] if axis == 1 else (u & (finite | hide))[j]
                    k = int(np.argmax(line))                 # 那条线上唯一看不见的格子
                    tier[j] = 0.0 if (this_risky[k] and k != i) else 1.0
                score = np.where(cand, tier * 1e18 + np.nan_to_num(line_vals), np.inf)
                j = int(np.argmin(score))
                if axis == 1:
                    secondary[i, j] = True
                else:
                    secondary[j, i] = True
                changed = True
                break                                        # 藏了一格就重新数：可能顺带解决了别的行、列
            if changed:
                break
        if not changed:
            break
    as_df = lambda a: pd.DataFrame(a, index=counts.index, columns=counts.columns)
    return as_df(primary), as_df(secondary)


# ══ 结果对象 ═══════════════════════════════════════════════════════════════
@dataclass
class MatrixPlot:
    """viz.matrix 的返回值。

    ax:         画在哪个 ax 上（m.ax.figure 就是整张图，交给 viz.finish）。
    counts:     排好序的原始矩阵（人数）。标题里的数从这里算，比如 m.counts.to_numpy().max()。
    values:     上色用的值：percent=None 时就是 counts，否则是占比（0~1）。
    shown:      每个格子实际写的文字（"1,234"、"<5"、"*"、""）。核对"图上有没有漏出小数字"就看它。
    suppressed: 布尔表，True = 人数 < min_value 被藏（写 "<5"）。
    secondary:  布尔表，True = 互补抑制多藏的（写 "*"）。
    texts:      {(行名, 列名): Text}，想单独改某一格的字（颜色、加粗）就从这里取。
    totals:     {"row": Series, "col": Series, "all": 数}，totals=True 时画在右边和下边的合计（没开是 None）。
    mesh:       上色的 QuadMesh：要色条时 fig.colorbar(m.mesh, ...)（或者直接 cbar=True）。
    """
    ax: plt.Axes
    counts: pd.DataFrame
    values: pd.DataFrame
    shown: pd.DataFrame
    suppressed: pd.DataFrame
    secondary: pd.DataFrame
    texts: dict = field(default_factory=dict)
    totals: dict | None = None
    mesh: object = None
    min_value: float | None = 5
    percent: str | None = None
    diagonal: str = "show"

    @property
    def note(self) -> str:
        """一句口径说明，抄进副标题：哪些符号是什么意思。没有藏格子时返回空字符串。"""
        parts = []
        if self.suppressed.to_numpy().any():
            parts.append(f"<{self.min_value:g} = 不足 {self.min_value:g} 人，不公布")
        if self.secondary.to_numpy().any():
            parts.append("* = 为防止由合计反推而一并隐去")
        if self.diagonal == "gray":
            parts.append("对角线（灰字）= 区内，不参与配色")
        elif self.diagonal == "hide":
            parts.append("对角线（区内）未显示")
        return "；".join(parts)

    @property
    def n_hidden(self) -> int:
        """一共藏了几个格子（<5 加 *）。"""
        return int(self.suppressed.to_numpy().sum() + self.secondary.to_numpy().sum())


# ══ 主函数 ═════════════════════════════════════════════════════════════════
def matrix(data: pd.DataFrame, ax=None, *, row: str | None = None, col: str | None = None, value: str | None = None,
           order=None, percent: str | None = None, min_value: float | None = 5, totals: bool = False,
           diagonal: str = "auto", hot: int | Iterable[tuple] = 0, fmt: str | Callable | None = None,
           norm: str | Normalize = "linear", cmap=None, cbar: bool = False, cbar_label: str = "",
           row_title: str | None = None, col_title: str | None = None, fontsize: float = 9,
           cell: tuple[float, float] = (0.62, 0.40), rotate: float | str = "auto") -> MatrixPlot:
    """画热力矩阵：每个格子按数值上色，格子里写数字。返回 MatrixPlot（见上面的类说明）。

    ── 数据 ──────────────────────────────────────────────────────────────
    data:     长表（一行一条记录）给 row=、col=、value= 三个列名，函数自己透视（同一格多条记录会相加）；
              宽表（行 = A、列 = B）三个都不给。
    order:    行列顺序。None = 按数据原样；"total" = 按合计从大到小（最常用）；
              列表 = 指定顺序（方阵时行列同序）；(行列表, 列列表) = 分别指定。
    percent:  None = 写人数；"row" = 每行加起来 100%（从 A 出发去了哪里）；"col" = 每列 100%（到 B 的人从哪来）；
              "all" = 全表 100%。占比的分母包含被藏的格子，所以是真实占比。

    ── 隐私（规范第 7 节）───────────────────────────────────────────────
    min_value: 人数小于它的格子写 "<5"、不上色（默认 5）。给 None 关掉——只在数不是人数时才这么做。
               开了 totals 或 percent="row"/"col"/"all" 时自动做互补抑制（写 "*"），原因见模块说明。

    ── 外观 ──────────────────────────────────────────────────────────────
    totals:   True 在右边加一列"合计"（每行），下边加一行"合计"（每列），右下角是总计。合计不上色。
    diagonal: 只对方阵（行列是同一组名字）有用。"auto"（默认）= 方阵时用 "gray"，否则 "show"；
              "show" 和别的格子一样；"gray" 灰底灰字、不参与配色（区内流动通常比跨区大得多，
              参与配色会把其他格子都压成浅色）；"hide" 不显示。
    hot:      强调最大的几个格子（加粗 + 深色边框）。给整数 = 前几名（不算对角线、不算被藏的）；
              给 [(行, 列), ...] = 指定哪几格。
    fmt:      格子里数字的写法。默认人数 "{:,.0f}"（千分位），占比按规范自动（40%、0.4%）。也可以给函数。
    norm:     "linear"（默认，从 0 起）| "log"（数值差好几个数量级时）| 自己的 Normalize。
    cmap:     色阶，默认主色浅 → 深（MAIN_LIGHT → MAIN → MAIN_DARK）。
    cbar:     True 加色条（cbar_label 是色条标题）。格子里已经写了数，一般不需要。
    row_title / col_title: 行、列分别是什么，比如 "居住区"、"工作区"。不给就用长表的列名。
    fontsize: 格子里文字的字号（磅），规范要求不小于 8。
    cell:     ax 不给、自动建图时，每个格子的宽和高（英寸）。
    rotate:   列名的旋转角度。"auto" = 放不下就斜 45°。

    ax 不给就新建一张图，大小按格子数算；给了 ax 就画在里面（ax 会被整个占用）。
    """
    # ── 0 参数检查：尽早报错，说清楚怎么改 ─────────────────────────────────
    if percent not in (None, "row", "col", "all"):
        raise ValueError(f"percent 只能是 None、'row'、'col'、'all'，拿到 {percent!r}")
    if diagonal not in ("auto", "show", "gray", "hide"):
        raise ValueError(f"diagonal 只能是 'auto'、'show'、'gray'、'hide'，拿到 {diagonal!r}")
    if fontsize < 8:
        warnings.warn(f"fontsize={fontsize} 小于 8 磅，不符合规范第 3 节（刻度、标注不小于 8 磅）", stacklevel=2)

    # ── 1 整理数据：宽表、排序、方阵判断 ────────────────────────────────────
    wide = _to_wide(data, row, col, value)
    if wide.empty:
        raise ValueError("矩阵是空的：检查一下筛选条件，或者 row/col/value 是不是给反了")
    square = _is_square(wide)
    counts = _apply_order(wide, order, square)
    square = _is_square(counts)                              # order 可能只挑了一部分行列：按排好的结果重新判断
    if diagonal == "auto":
        diagonal = "gray" if square else "show"
    elif diagonal != "show" and not square:
        warnings.warn("行和列不是同一组名字，没有对角线；diagonal 参数不起作用", stacklevel=2)
        diagonal = "show"
    nr, nc = counts.shape
    D = np.zeros(counts.shape, bool)                       # 对角线：行名 = 列名的格子（只有方阵才有）
    if square:
        pos = {n: j for j, n in enumerate(counts.columns)}
        for i, n in enumerate(counts.index):
            D[i, pos[n]] = True
    diag = pd.DataFrame(D, index=counts.index, columns=counts.columns)

    # ── 2 占比 ─────────────────────────────────────────────────────────────
    c = counts.to_numpy(float)
    if percent == "row":
        denom = np.nansum(c, axis=1, keepdims=True)
    elif percent == "col":
        denom = np.nansum(c, axis=0, keepdims=True)
    elif percent == "all":
        denom = np.full((1, 1), np.nansum(c))
    else:
        denom = None
    with np.errstate(invalid="ignore", divide="ignore"):
        v = c / denom if denom is not None else c.copy()
    values = pd.DataFrame(v, index=counts.index, columns=counts.columns)

    # ── 3 要藏哪些格子 ─────────────────────────────────────────────────────
    know_rows = totals or percent in ("row", "all")          # 读者知道每行的合计（或每行 100%）
    know_cols = totals or percent in ("col", "all")
    hidden = diag if diagonal == "hide" else None
    primary, secondary = suppress_cells(counts, min_value, rows=know_rows, cols=know_cols, hidden=hidden)
    P, S = primary.to_numpy(bool), secondary.to_numpy(bool)
    nan = ~np.isfinite(c)

    # ── 4 色阶：只用"正常上色"的格子定范围 ──────────────────────────────────
    colored = ~nan & ~P & ~S & ~(D & (diagonal in ("gray", "hide")))
    cv = v[colored]
    if isinstance(norm, Normalize):
        nm = norm
    elif norm == "log":
        pos = cv[cv > 0]
        nm = LogNorm(pos.min() if len(pos) else 1, pos.max() if len(pos) else 10)
    elif norm == "linear":
        top = float(cv.max()) if len(cv) and cv.max() > 0 else 1.0
        nm = Normalize(0, top)
    else:
        raise ValueError("norm 只能是 'linear'、'log' 或 Normalize 对象")
    cmap = plt.get_cmap(cmap) if isinstance(cmap, str) else (
        cmap or LinearSegmentedColormap.from_list("matrix", [MAIN_LIGHT, MAIN_MID, MAIN, MAIN_DARK]))

    # ── 5 建图 ─────────────────────────────────────────────────────────────
    row_title = row_title if row_title is not None else (row or counts.index.name or "")
    col_title = col_title if col_title is not None else (col or counts.columns.name or "")
    if ax is None:
        lw = max(len(s) for s in counts.index) * fontsize / 72 * 1.1 + 0.6        # 行名占的宽度（英寸）
        lh = max(len(s) for s in counts.columns) * fontsize / 72 * 0.8 + 0.6      # 列名可能斜着放，留高一点
        w = (nc + (1 if totals else 0)) * cell[0] + lw + 0.4
        h = (nr + (1 if totals else 0)) * cell[1] + lh + (0.7 if cbar else 0.2)
        _, ax = plt.subplots(figsize=(w, h), layout="constrained")

    # ── 6 上色：pcolormesh，格子之间留白线 ──────────────────────────────────
    masked = np.ma.masked_array(v, mask=~colored)
    mesh = ax.pcolormesh(np.arange(nc + 1), np.arange(nr + 1), masked, cmap=cmap, norm=nm,
                         edgecolors="white", linewidth=1.5, zorder=1)
    for i in range(nr):                                      # 不上色的格子各自的底色
        for j in range(nc):
            if colored[i, j] or nan[i, j] or (D[i, j] and diagonal == "hide"):
                continue
            bg = DIAG_BG if (D[i, j] and diagonal == "gray" and not (P[i, j] or S[i, j])) else SMALL_BG
            ax.add_patch(Rectangle((j, i), 1, 1, fc=bg, ec="white", lw=1.5, zorder=0.9))

    # ── 7 格子里的字 ───────────────────────────────────────────────────────
    f = _as_formatter(fmt if fmt is not None else (fmt_pct if percent else "{:,.0f}"))
    shown = pd.DataFrame("", index=counts.index, columns=counts.columns)
    texts = {}
    for i, rn in enumerate(counts.index):
        for j, cn in enumerate(counts.columns):
            if nan[i, j] or (D[i, j] and diagonal == "hide"):
                continue
            if P[i, j]:
                s, color, weight = f"<{min_value:g}", MUTED, "normal"
            elif S[i, j]:
                s, color, weight = "*", MUTED, "normal"
            elif D[i, j] and diagonal == "gray":
                s, color, weight = f(v[i, j]), MUTED, "normal"
            else:
                s, weight = f(v[i, j]), "normal"
                r, g, b = to_rgb(cmap(nm(v[i, j])))
                color = INK if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else "white"   # 深色格子写白字
            shown.iloc[i, j] = s
            texts[(rn, cn)] = ax.text(j + 0.5, i + 0.5, s, ha="center", va="center", fontsize=fontsize,
                                      color=color, fontweight=weight, zorder=3)

    # ── 8 强调 hot ─────────────────────────────────────────────────────────
    if isinstance(hot, (int, np.integer)) and not isinstance(hot, bool):
        order_idx = np.argsort(np.where(colored & ~D, v, -np.inf), axis=None)[::-1][:int(hot)]
        hot_cells = [divmod(int(k), nc) for k in order_idx if (colored & ~D).ravel()[k]]
    else:
        pos_r = {n: i for i, n in enumerate(counts.index)}
        pos_c = {n: j for j, n in enumerate(counts.columns)}
        hot_cells = []
        for rn, cn in hot:
            if str(rn) not in pos_r or str(cn) not in pos_c:
                raise KeyError(f"hot 里的 ({rn!r}, {cn!r}) 不在矩阵里")
            hot_cells.append((pos_r[str(rn)], pos_c[str(cn)]))
    for i, j in hot_cells:
        ax.add_patch(Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, fill=False, ec=INK, lw=1.6, zorder=2.5))
        t = texts.get((counts.index[i], counts.columns[j]))
        if t is not None:
            t.set_fontweight("bold")

    # ── 9 合计 ─────────────────────────────────────────────────────────────
    tot = None
    if totals:
        rs, cs = counts.sum(axis=1, min_count=1), counts.sum(axis=0, min_count=1)
        tot = {"row": rs, "col": cs, "all": float(np.nansum(c))}
        tf = _as_formatter("{:,.0f}")
        small = lambda x: min_value is not None and np.isfinite(x) and x < min_value
        show_t = lambda x: "" if not np.isfinite(x) else (f"<{min_value:g}" if small(x) else tf(x))
        gap = 0.15
        for i, x in enumerate(rs):
            ax.text(nc + gap + 0.5, i + 0.5, show_t(x), ha="center", va="center", fontsize=fontsize,
                    color=INK, fontweight="bold", zorder=3)
        for j, x in enumerate(cs):
            ax.text(j + 0.5, nr + gap + 0.5, show_t(x), ha="center", va="center", fontsize=fontsize,
                    color=INK, fontweight="bold", zorder=3)
        ax.text(nc + gap + 0.5, nr + gap + 0.5, show_t(tot["all"]), ha="center", va="center",
                fontsize=fontsize, color=INK, fontweight="bold", zorder=3)
        ax.plot([nc + gap / 2] * 2, [0, nr + 1 + gap], color=GRAY, lw=0.8, zorder=2)      # 分隔线
        ax.plot([0, nc + 1 + gap], [nr + gap / 2] * 2, color=GRAY, lw=0.8, zorder=2)

    # ── 10 坐标轴：列名放上面（先读列名再往下看），行名放左边 ─────────────────
    ext = 1.15 if totals else 0
    ax.set_xlim(0, nc + ext)
    ax.set_ylim(nr + ext, 0)                                 # 第一行在最上面
    ax.set_aspect("auto")
    xt = list(counts.columns) + (["合计"] if totals else [])
    yt = list(counts.index) + (["合计"] if totals else [])
    ax.set_xticks([j + 0.5 for j in range(nc)] + ([nc + 0.15 + 0.5] if totals else []))
    ax.set_yticks([i + 0.5 for i in range(nr)] + ([nr + 0.15 + 0.5] if totals else []))
    if rotate == "auto":
        fig_w = ax.figure.get_figwidth() * ax.get_position().width
        cell_pt = fig_w / (nc + ext) * 72
        rotate = 45 if max(len(s) for s in xt) * fontsize * 1.05 > cell_pt * 0.95 else 0
    ax.set_xticklabels(xt, rotation=rotate, ha="left" if rotate else "center",
                       rotation_mode="anchor" if rotate else "default", fontsize=max(fontsize, 9))
    ax.set_yticklabels(yt, fontsize=max(fontsize, 9))
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.tick_params(length=0, pad=4)
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    if col_title:
        ax.set_xlabel(col_title, fontsize=10, color=MUTED, labelpad=8)
    if row_title:
        ax.set_ylabel(row_title, fontsize=10, color=MUTED, labelpad=8)

    if cbar:
        cb = ax.figure.colorbar(mesh, ax=ax, orientation="horizontal", shrink=0.6, aspect=30, pad=0.03)
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=9, length=0)
        if percent:
            cb.ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: fmt_pct(x)))
        cb.set_label(cbar_label, fontsize=9.5, color=INK)

    return MatrixPlot(ax=ax, counts=counts, values=values, shown=shown, suppressed=primary, secondary=secondary,
                      texts=texts, totals=tot, mesh=mesh, min_value=min_value, percent=percent, diagonal=diagonal)
