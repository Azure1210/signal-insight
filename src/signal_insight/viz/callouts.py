#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : callouts.py
# @Path       : signal-insight/src/signal_insight/viz/callouts.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-14 16:00:00
# @Version    : v1.3.0
# @Description: 引线标注：自动排版（按中线分左右、按纬度排上下、等距铺满）、参数包 LabelLayout、逐条样式、自检
# @ChangeLog:
#   2026-10-14 16:00:00 | Matri | v1.0.0 | 从 maps.py 拆出：标注位置的改动原因（调标注、换参数包）和地图几何不同（AGENTS.md 第 2 条）
#   2026-10-14 20:00:00 | Matri | v1.1.0 | 自动排版默认改为 span：按地图经度中线分左右、按落点纬度排上下；可选固定角度拐点 angle；
#                                          名字/数值/引线/落点四部分各自可设样式、可隐藏，可逐条覆盖（each）
#   2026-10-14 22:00:00 | Matri | v1.2.0 | 默认色改从 viz.maps.colors 取，不再依赖 theme.py
#   2026-10-15 10:00:00 | Matri | v1.3.0 | 新增区内标注 RegionTexts；Callouts 可跳过区内已放下的名字（inside="auto"）；
#                                          空数据不再报错；两种标注共用一套样式规则

"""引线标注。一条引线三个点：起点（文字那端）—横线— 拐点 —斜线— 终点（区内落点）。

位置从两处来：自动排版给一个起点方案；人工改过、定下来的方案叫"参数包"（LabelLayout），存成 JSON，
同一张底图的所有图都用它，只换文字。
样式（颜色、粗细、线型、显示与否）不进参数包：位置是底图的属性，样式是这张图、这个主题的属性——
同一份参数包换主题、换强调对象都不用重存。
用法见 maps.py 开头，入口是 Regions.label()。不 import maps：maps 用这里的东西，反过来不用。
"""
from __future__ import annotations

import json
import math
import pathlib
import warnings
from dataclasses import dataclass, replace
from importlib.resources import files
from itertools import combinations
from typing import Callable, Mapping

import numpy as np
from matplotlib import cbook, patheffects
from matplotlib.artist import Artist, allow_rasterization
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.transforms import Bbox, IdentityTransform

from .mapcolors import colors as MC        # 地图自己的颜色，不读 theme（见 mapcolors.py）

__all__ = ["FURNITURE", "PARTS", "Leader", "LabelLayout", "Callouts", "RegionTexts"]

FURNITURE = "viz.maps.furniture"   # 比例尺、指北针这类"地图附件"的 gid：引线标注排版时会让开它们。
                                   # 自己加的图例、注记想让标注让开，也可以 artist.set_gid(viz.maps.FURNITURE)

PARTS = ("name", "value", "line", "dot")        # 一条标注的四个部分：名字、数值、引线、落点
_KIND = {"name": Text, "value": Text, "line": Line2D, "dot": Line2D}


def _xy(p) -> tuple[float, float]:
    x, y = (float(v) for v in p)
    return x, y


@dataclass
class Leader:
    """一条引线的位置。坐标都是 (lng, lat)。

    side:  "left" | "right"，文字在拐点的哪一侧（左列文字右对齐，右列左对齐）。
    elbow: 拐点。end: 终点（区内落点，引线最后扎进去的那一点）。
    start: 起点（短横线靠文字那端）。不给 = 从拐点水平向外 stub 磅，同一列的起点自然对齐。
    stub:  起点到拐点的长度（磅），只在没给 start 时用；不给就用整份参数包的 stub。
    """
    side: str
    elbow: tuple[float, float]
    end: tuple[float, float]
    start: tuple[float, float] | None = None
    stub: float | None = None

    def __post_init__(self):
        if self.side not in ("left", "right"):
            raise ValueError(f"side 只能是 'left' / 'right'，拿到 {self.side!r}")
        self.elbow, self.end = _xy(self.elbow), _xy(self.end)
        self.start = None if self.start is None else _xy(self.start)
        self.stub = None if self.stub is None else float(self.stub)


class LabelLayout:
    """引线参数包：{名字: Leader}，加上整份共用的 stub（起点到拐点）和 gap（文字到起点），单位磅。

    同一张底图调好一次，以后所有图都用它，只换文字：
        lay = co.freeze()                                   # 自动排好的一版定下来
        lay.swap("和平区", "辽中区").move("新民市", dy=-0.05)  # 改几条（返回自己，可以连着写）
        lay.edit("浑南区", end=(123.52, 41.70), stub=40)
        lay.save("viz/layouts/shenyang_districts.json")     # 一个名字一行，方便手改、方便看 diff
        geo.label(ax, texts, layout="shenyang_districts")   # 以后每张图
    """

    _FIELDS = ("side", "elbow", "end", "start", "stub")

    def __init__(self, leaders: Mapping[str, Leader | Mapping] = (), *, stub: float = 28, gap: float = 4):
        self.leaders = {str(n): v if isinstance(v, Leader) else Leader(**v) for n, v in dict(leaders).items()}
        self.stub, self.gap = float(stub), float(gap)

    # ---------------------------------------------------------------- 读写
    @classmethod
    def from_dict(cls, d: Mapping) -> "LabelLayout":
        return cls(d.get("labels", {}), stub=d.get("stub", 28), gap=d.get("gap", 4))

    @classmethod
    def load(cls, path) -> "LabelLayout":
        return cls.from_dict(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        r = lambda p: [round(p[0], 5), round(p[1], 5)]
        labels = {}
        for n, v in self.leaders.items():
            d = {"side": v.side, "elbow": r(v.elbow), "end": r(v.end)}
            if v.start is not None:
                d["start"] = r(v.start)
            if v.stub is not None:
                d["stub"] = v.stub
            labels[n] = d
        return {"stub": self.stub, "gap": self.gap, "labels": labels}

    def save(self, path) -> pathlib.Path:
        """存成 JSON：一个名字一行。"""
        d, dump = self.to_dict(), (lambda o: json.dumps(o, ensure_ascii=False))
        rows = ",\n".join(f"    {dump(n)}: {dump(v)}" for n, v in d["labels"].items())
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'{{\n  "stub": {dump(d["stub"])},\n  "gap": {dump(d["gap"])},\n'
                        f'  "labels": {{\n{rows}\n  }}\n}}\n', encoding="utf-8")
        return path

    # ---------------------------------------------------------------- 改
    def edit(self, name: str, **changes) -> "LabelLayout":
        """改一条的任意字段：edit("和平区", elbow=(122.30, 41.90), end=..., start=..., stub=36, side="right")。
        给 start=None 就回到"从拐点水平向外 stub 磅"。名字不在包里时新加一条（这时 side、elbow、end 都要给）。"""
        if unknown := set(changes) - set(self._FIELDS):
            raise TypeError(f"Leader 没有字段 {sorted(unknown)}；可改 {', '.join(self._FIELDS)}")
        name = str(name)
        self.leaders[name] = replace(self.leaders[name], **changes) if name in self.leaders else Leader(**changes)
        return self

    def swap(self, a: str, b: str) -> "LabelLayout":
        """两条对调位置（侧、拐点、起点、短横线长），各自的终点不变。两条引线交叉、或者一条绕远时最常用。"""
        la, lb = self[a], self[b]
        self.leaders[str(a)], self.leaders[str(b)] = replace(lb, end=la.end), replace(la, end=lb.end)
        return self

    def move(self, name: str, dx: float = 0.0, dy: float = 0.0) -> "LabelLayout":
        """拐点（以及手动给过的起点）平移 (dx, dy) 度，文字跟着走。上下挪用 dy。"""
        v = self[name]
        shift = lambda p: None if p is None else (p[0] + dx, p[1] + dy)
        self.leaders[str(name)] = replace(v, elbow=shift(v.elbow), start=shift(v.start))
        return self

    # ---------------------------------------------------------------- 查
    def __getitem__(self, name) -> Leader:
        try:
            return self.leaders[str(name)]
        except KeyError:
            raise KeyError(f"参数包里没有 {name!r}；有 {', '.join(self.leaders)}") from None

    def __contains__(self, name) -> bool:
        return str(name) in self.leaders

    def __iter__(self):
        return iter(self.leaders)

    def __len__(self) -> int:
        return len(self.leaders)

    def __repr__(self) -> str:
        rows = [f"LabelLayout（{len(self)} 条，stub={self.stub:g} 磅，gap={self.gap:g} 磅）"]
        for n, v in self.leaders.items():
            extra = (f"  起点 ({v.start[0]:.4f}, {v.start[1]:.4f})" if v.start else "") + \
                    (f"  stub {v.stub:g}" if v.stub is not None else "")
            rows.append(f"  {n}\t{'左' if v.side == 'left' else '右'}  拐点 ({v.elbow[0]:.4f}, {v.elbow[1]:.4f})"
                        f"  终点 ({v.end[0]:.4f}, {v.end[1]:.4f}){extra}")
        return "\n".join(rows)


_LAYOUTS = files(__package__) / "layouts"                # 随包安装的参数包（和 styles/ 一样要写进 package data）


def _as_layout(layout) -> LabelLayout:
    """LabelLayout / JSON 文件路径 / viz/layouts/ 下的名字 → LabelLayout。"""
    if isinstance(layout, LabelLayout):
        return layout
    if isinstance(layout, Mapping):
        return LabelLayout.from_dict(layout)
    p = pathlib.Path(layout)
    if p.suffix == ".json" and p.is_file():
        return LabelLayout.load(p)
    builtin = _LAYOUTS / f"{layout}.json"
    if builtin.is_file():
        return LabelLayout.from_dict(json.loads(builtin.read_text(encoding="utf-8")))
    raise FileNotFoundError(f"找不到参数包 {layout!r}：给 LabelLayout、.json 文件路径，或 viz/layouts/ 下的文件名")


def _even_rows(target: list[float], row: float, lo: float, hi: float, fill: bool = False,
               outer: tuple[float, float] | None = None) -> np.ndarray:
    """一列等距的行位，从上到下（像素，y 向上）。行距至少 row（一行字高 + 空隙），整列在 [lo, hi] 内。
    fill=True：铺满 [lo, hi]（span）；fill=False：行距和整列位置用最小二乘拟合各行目标高度（fit）。
    放不下时：先在 outer（能用的最大范围，一般是 ax 上下沿）里往外扩，还放不下才整列居中、上下等量溢出。"""
    y, n = np.asarray(target, float), len(target)
    if n == 1:
        return np.array([np.clip(y[0], lo, hi) if lo <= hi else (lo + hi) / 2])
    i = np.arange(n)
    d = max((hi - lo) / (n - 1) if fill else -np.polyfit(i, y, 1)[0], row)
    need = d * (n - 1)
    if need > hi - lo:                                                  # 放不下
        flo, fhi = outer or (lo, hi)
        if need <= fhi - flo:                                           # 往外扩：中心尽量不动
            top = float(np.clip((lo + hi) / 2 + need / 2, flo + need, fhi))
        else:
            top = (flo + fhi) / 2 + need / 2
    else:
        top = float(np.clip(hi if fill else np.mean(y + i * d), lo + need, hi))
    return top - i * d


def _seg_cross(p1, p2, p3, p4) -> bool:
    ccw = lambda a, b, c: (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])
    return ccw(p1, p3, p4) * ccw(p2, p3, p4) < 0 and ccw(p1, p2, p3) * ccw(p1, p2, p4) < 0


def _poly_cross(p, q) -> bool:
    """两条折线（起点、拐点、终点）有没有交叉。固定角度时横线也伸进地图，所以两段都要查。"""
    return any(_seg_cross(p[i], p[i + 1], q[j], q[j + 1]) for i in range(len(p) - 1) for j in range(len(q) - 1))


def _props(spec, part: str, where: str) -> dict:
    """样式参数 → matplotlib 的关键字（别名统一成全名，lw 和 linewidth 不会打架）。False = 不显示。"""
    if spec is None or spec is True:
        return {}
    if spec is False:
        return {"visible": False}
    if not isinstance(spec, Mapping):
        raise TypeError(f"{where} 应是 dict（matplotlib 的样式参数）、True 或 False，拿到 {type(spec).__name__}")
    return cbook.normalize_kwargs(dict(spec), _KIND[part])


def _part_styles(items, props, each, hot, fs: float, extra: Mapping | None = None) -> dict[str, dict[str, dict]]:
    """每条标注四个部分的最终样式：默认 < 整体（props）< 强调（hot）< 逐条（each）。默认色此刻从 viz.maps.colors 取。
    extra: {部分: 样式} 改默认值（区内标注用它加白边）。Callouts 和 RegionTexts 共用，两种标注的样式写法完全一样。"""
    n_ = lambda part, d: cbook.normalize_kwargs(d, _KIND[part])
    base = {"name": n_("name", dict(fontsize=fs, color=MC.ink)),
            "value": n_("value", dict(fontsize=fs, color=MC.ink)),
            "line": n_("line", dict(color=MC.line, lw=0.45, solid_joinstyle="round", dash_joinstyle="round",
                                    solid_capstyle="butt", dash_capstyle="butt")),   # 细、灰，不和区界抢
            "dot": n_("dot", dict(marker="o", ms=2.2, color=MC.ink, mec="white", mew=0.4, ls=""))}
    for p, d in (extra or {}).items():
        base[p] = {**base[p], **n_(p, d)}
    props = dict(props or {})
    if bad := set(props) - set(PARTS):
        raise TypeError(f"样式部分只有 {', '.join(PARTS)}，拿到 {sorted(bad)}")
    glob = {p: {**base[p], **_props(props.get(p), p, f"{p}props")} for p in PARTS}
    strong = {"color": MC.hot, "fontweight": "bold"}                  # 一种颜色强调一件事
    hot = set(map(str, hot))
    each = {str(k): v for k, v in (each or {}).items()}
    out = {}
    for n in items:
        own = each.get(n) or {}
        if not isinstance(own, Mapping):
            raise TypeError(f"each[{n!r}] 应是 {{部分: 样式}}，部分是 {', '.join(PARTS)}；整条不画请直接不传这个名字")
        if bad := set(own) - set(PARTS):
            raise TypeError(f"each[{n!r}] 里的部分只有 {', '.join(PARTS)}，拿到 {sorted(bad)}")
        out[n] = {p: {**glob[p], **(strong if n in hot and p in ("name", "value") else {}),
                      **_props(own.get(p), p, f"each[{n!r}][{p!r}]")} for p in PARTS}
    return out


def _fmt_value(fmt, value) -> str:
    return fmt(value) if callable(fmt) else fmt.format(value)


@dataclass
class _Auto:
    """自动排版要用的东西：终点、分侧、地图东西两沿（经度）、铺法、拐点离外缘和行间空隙（磅）、斜线角度。"""
    anchors: dict
    sides: dict
    x_edges: tuple[float, float]
    spread: str = "span"
    elbow: float = 14
    pad: float = 3
    angle: float | None = None
    uncross: bool = True
    margin: float = 0.04                    # span 时上下各多铺 ax 高的这么多


class Callouts(Artist):
    """一组左右两列的引线标注，由 Regions.label() 创建并加到 ax 上。

    四个部分按名字取，都是 matplotlib 自己的对象，可以继续改：
        co.texts[名字]  名字（Text）      co.nums[名字]  数值（Text，有数值的才有）
        co.lines[名字]  引线（Line2D）    co.dots[名字]  落点（Line2D）

    位置从哪来：
      · 套参数包：全按 LabelLayout 画。参数包是活的——改它（swap / move / edit）之后再显示图，就是改过的样子；
      · 自动：每次绘制按当时的像素排一遍（图缩放、tight_layout 挪动、存 300 dpi 都会重排）：
          1. 分侧：落点在地图经度中线以西进左列、以东进右列（Regions.label 的 split 可改）；
          2. 上下：每列按落点纬度从北到南排；
          3. 行位：两列都铺满全部落点的上下范围再等距（span）；一列太挤时先往外扩到 ax 上下沿，还不够才溢出；
          4. 拐点：angle=None 时同一列的拐点在一条竖线上（地图外缘外 elbow 磅）；
             angle=度数 时所有斜线都是这个角度（相对水平），彼此平行，拐点沿横线往里收；
          5. 按纬度排仍可能交叉（一个离列很远的点夹在两个近点中间时），交叉就对调两者再排（uncross）；
          6. 行位让开同侧的地图附件（gid 为 FURNITURE 的元素：右上角指北针、左下角比例尺）。
        满意了用 freeze() 定成参数包。
    get_tightbbox 返回文字范围，排版引擎据此在 ax 外侧留位置。颜色在创建时从 viz.maps.colors 取定。
    """

    def __init__(self, ax, items: Mapping[str, tuple[str, float | None]], *, props: Mapping | None = None,
                 each: Mapping | None = None, hot=(), fmt: str | Callable = "{:,.0f}", sep: float = 3,
                 fs: float = 9, debug: bool = False, layout: LabelLayout | None = None,
                 auto: _Auto | None = None, stub: float = 28, gap: float = 4,
                 skip: Callable | None = None):
        super().__init__()
        self.axes = ax
        self.set_figure(ax.figure)
        self.set_clip_on(False)
        self.set_zorder(5)
        self._layout_obj, self._auto, self._debug = layout, auto, debug
        self._skip = skip                            # skip(名字, renderer) 为真就不排这条（inside="auto" 时已写进区内）
        self._stub, self._gap = (layout.stub, layout.gap) if layout else (float(stub), float(gap))
        self._sep = float(sep)
        self._data: dict[str, tuple] = {}            # 最近一次排版：{名字: (side, 起点, 拐点, 终点, 起点是否单给)}，经纬度
        self._warned = False
        self._debug_color = MC.debug
        styles = _part_styles(items, props, each, hot, fs)

        self.texts: dict[str, Text] = {}
        self.nums: dict[str, Text] = {}
        self.lines: dict[str, Line2D] = {}
        self.dots: dict[str, Line2D] = {}
        ident = IdentityTransform()
        for n, (label, value) in items.items():
            st = styles[n]
            self.texts[n] = self._make(Text(0, 0, label), st["name"], n, "name",
                                       transform=ident, clip_on=False, va="baseline")
            if value is not None:
                self.nums[n] = self._make(Text(0, 0, _fmt_value(fmt, value)), st["value"], n, "value",
                                          transform=ident, clip_on=False, va="baseline")
            self.lines[n] = self._make(Line2D([], []), st["line"], n, "line", transform=ident, clip_on=False)
            self.dots[n] = self._make(Line2D([], []), st["dot"], n, "dot", transform=ax.transData, clip_on=False)

    def _make(self, artist, style: dict, name: str, part: str, **fixed):
        try:
            artist.update(style)
        except AttributeError as e:
            raise AttributeError(f"{name} 的 {part} 样式：{e}") from None
        artist.update(fixed)                                            # 位置相关的设置不让改：排版靠它们
        artist.set_figure(self.axes.figure)
        return artist

    def _parts(self, n: str) -> list:
        return [a for a in (self.lines[n], self.dots[n], self.texts[n], self.nums.get(n)) if a is not None]

    def _children(self):
        return [a for n in self._data for a in self._parts(n)]

    # ---------------------------------------------------------------- 参数包
    @property
    def layout(self) -> LabelLayout:
        """当前的参数包。套参数包时就是传进来的那个（改它会反映到图上）；自动排版时是最近一次绘制结果的快照。"""
        if self._layout_obj is not None:
            return self._layout_obj
        if not self._data:
            self._layout(self.figure._get_renderer())
        return LabelLayout({n: Leader(side, elbow, end, start if explicit else None)
                            for n, (side, start, elbow, end, explicit) in self._data.items()},
                           stub=self._stub, gap=self._gap)

    def freeze(self) -> LabelLayout:
        """把自动排版的当前结果定下来：之后按参数包画，返回它。改它（swap / move / edit）再显示图就是改过的样子，
        save() 存下来给以后的图用。取之前先把图画一遍（finish 存图、或在 notebook 里显示过），坐标才是最终版面的。"""
        if self._layout_obj is None:
            self._layout_obj = self.layout
        return self._layout_obj

    # ---------------------------------------------------------------- 排版
    def _active(self, renderer) -> list[str]:
        """这次要排的名字：去掉 skip 判定为不排的（inside="auto" 时，区内放得下的那些）。"""
        return [n for n in self.texts if self._skip is None or not self._skip(n, renderer)]

    def _text_parts(self, n: str) -> list[Text]:
        return [t for t in (self.texts[n], self.nums.get(n)) if t is not None and t.get_visible() and t.get_text()]

    def _row_height(self, n: str, renderer) -> float:
        return max((t.get_window_extent(renderer).height for t in self._text_parts(n)), default=0.0)

    @staticmethod
    def _elbow(a, y: float, ex: float, sign: int, angle: float | None) -> np.ndarray:
        """拐点（像素）。angle=None：在列线上；否则斜线按 angle 度走到这一行的高度，走不到列线外（太陡时停在列线上）。"""
        if angle is None:
            return np.array([ex, y])
        x = a[0] + sign * abs(y - a[1]) / math.tan(math.radians(angle))
        return np.array([min(x, ex) if sign > 0 else max(x, ex), y])

    def _auto_rows(self, renderer) -> dict[str, tuple]:
        """自动排版，返回 {名字: (side, 起点, 拐点, 终点, 起点是否单给)}，像素。"""
        ax, au = self.axes, self._auto
        to_px, px = ax.transData.transform, renderer.points_to_pixels
        elbow, pad, stub = px(au.elbow), px(au.pad), px(self._stub)
        y_any = ax.get_ylim()[0]                                        # 经纬度 → 像素在 x、y 上互不影响
        (left, _), (right, _) = to_px([(au.x_edges[0], y_any), (au.x_edges[1], y_any)])
        active = self._active(renderer)
        if not active:
            return {}
        a = {n: to_px(au.anchors[n]) for n in active}
        span = None
        if au.spread == "span":                                         # 两列都铺满全部落点的上下范围
            ys, m = [p[1] for p in a.values()], au.margin * ax.bbox.height
            span = (min(ys) - m, max(ys) + m)
        out = {}
        for side, ex, sign in (("left", left - elbow, -1), ("right", right + elbow, 1)):
            names = [n for n in active if au.sides[n] == side]
            if not names:
                continue
            row = max(self._row_height(n, renderer) for n in names) + pad
            flo, fhi = self._free_range(renderer, side, pad)
            lo, hi = (max(flo, span[0]), min(fhi, span[1])) if span else (flo, fhi)
            lo, hi, flo, fhi = lo + row / 2, hi - row / 2, flo + row / 2, fhi - row / 2

            def geom(order):
                ys = _even_rows([a[n][1] for n in order], row, lo, hi, fill=bool(span), outer=(flo, fhi))
                return {n: (np.array([ex + sign * stub, y]), self._elbow(a[n], y, ex, sign, au.angle), a[n])
                        for n, y in zip(order, ys)}

            def first_cross(order, g):
                return next(((i, j) for i, j in combinations(range(len(order)), 2)
                             if _poly_cross(g[order[i]], g[order[j]])), None)

            order = sorted(names, key=lambda n: -a[n][1])               # 北 → 南
            g = geom(order)
            if au.uncross:
                best = (sum(_poly_cross(g[p], g[q]) for p, q in combinations(order, 2)), g)
                for _ in range(len(order) ** 2):
                    hit = first_cross(order, g)
                    if hit is None:
                        break
                    i, j = hit
                    order[i], order[j] = order[j], order[i]
                    g = geom(order)
                    k = sum(_poly_cross(g[p], g[q]) for p, q in combinations(order, 2))
                    if k < best[0]:
                        best = (k, g)
                else:
                    g = best[1]                                         # 消不干净就取交叉最少的那次
            out.update({n: (side, s, e, p, not np.isclose(e[0], ex)) for n, (s, e, p) in g.items()})
        return out

    def _free_range(self, renderer, side: str, pad: float) -> tuple[float, float]:
        """这一列能用的上下范围（像素）：ax 的上下沿，再让开同一侧的地图附件——上半部的压低上沿，下半部的抬高下沿。"""
        ax = self.axes
        lo, hi = ax.bbox.y0, ax.bbox.y1
        xc, yc = (ax.bbox.x0 + ax.bbox.x1) / 2, (ax.bbox.y0 + ax.bbox.y1) / 2
        for a in ax.get_children():
            if a.get_gid() != FURNITURE or not a.get_visible():
                continue
            b = a.get_window_extent(renderer)
            if ((b.x0 + b.x1) / 2 > xc) != (side == "right"):
                continue
            if (b.y0 + b.y1) / 2 > yc:
                hi = min(hi, b.y0 - pad)
            else:
                lo = max(lo, b.y1 + pad)
        return lo, hi

    def _place_text(self, n: str, side: str, s, renderer) -> None:
        """名字和数值排成一行：右列从起点往右写\"名字 数值\"，左列从起点往左写（仍是\"名字 数值\"的顺序）。
        两段共用一条基线（字号不同也对齐），这一行最大那段的视觉中心对准横线。"""
        px = renderer.points_to_pixels
        parts = self._text_parts(n)
        for t in (self.texts[n], self.nums.get(n)):
            if t is not None:
                t.set_position((s[0], s[1]))                            # 隐藏的也放到附近，免得被排版引擎算到远处
        if not parts:
            return
        big = max(parts, key=lambda t: t.get_fontsize())
        big.set_position((0, 0))
        ext = big.get_window_extent(renderer)
        yb = s[1] - (ext.y0 + ext.y1) / 2                               # 基线 = 横线高度 - 字框中心到基线的距离
        x, step = s[0] + (px(self._gap) if side == "right" else -px(self._gap)), px(self._sep)
        for t in (parts if side == "right" else parts[::-1]):
            t.set_horizontalalignment("left" if side == "right" else "right")
            t.set_position((x, yb))
            w = t.get_window_extent(renderer).width + step
            x += w if side == "right" else -w

    def _layout(self, renderer) -> None:
        """排一遍，写进各个 Text / Line2D，并把结果按经纬度记下（存图时 dpi 会变，像素不能留到下次用）。"""
        to_px, px = self.axes.transData.transform, renderer.points_to_pixels
        lay = self._layout_obj
        if lay is None:
            rows = self._auto_rows(renderer)
        else:
            rows = {}
            for n in self._active(renderer):
                if n not in lay:
                    continue
                v = lay[n]
                e, a = to_px(v.elbow), to_px(v.end)
                if v.start is not None:
                    s, explicit = to_px(v.start), True
                else:
                    sign = -1 if v.side == "left" else 1
                    s, explicit = np.array([e[0] + sign * px(self._stub if v.stub is None else v.stub), e[1]]), False
                rows[n] = (v.side, s, e, a, explicit)
        to_data = self.axes.transData.inverted().transform
        self._data = {}
        for n, (side, s, e, a, explicit) in rows.items():
            self._place_text(n, side, s, renderer)
            self.lines[n].set_data([s[0], e[0], a[0]], [s[1], e[1], a[1]])
            end = to_data(a)
            self.dots[n].set_data([end[0]], [end[1]])
            self._data[n] = (side, tuple(to_data(s)), tuple(to_data(e)), tuple(end), explicit)

    def _label_box(self, n: str, renderer) -> Bbox | None:
        boxes = [t.get_window_extent(renderer) for t in self._text_parts(n)]
        return Bbox.union(boxes) if boxes else None

    def _check(self, renderer) -> None:
        """自检（每个标注对象只警告一次）：文字互相重叠、文字压到地图附件、同一列两条引线交叉。
        自动排版一般不会触发；手改参数包、或套到比调参数包时更小的图上时，用它提醒。"""
        if self._warned:
            return
        to_px = self.axes.transData.transform
        boxes = {n: b for n in self._data if (b := self._label_box(n, renderer)) is not None}
        furniture = [a.get_window_extent(renderer) for a in self.axes.get_children()
                     if a.get_gid() == FURNITURE and a.get_visible()]
        problems = [f"{a} 和 {b} 的文字重叠" for a, b in combinations(boxes, 2) if boxes[a].overlaps(boxes[b])]
        problems += [f"{n} 的文字压到了指北针或比例尺" for n, b in boxes.items() if any(b.overlaps(f) for f in furniture)]
        for a, b in combinations(self._data, 2):
            da, db = self._data[a], self._data[b]
            if da[0] == db[0] and _poly_cross(to_px(da[1:4]), to_px(db[1:4])):
                problems.append(f"{a} 和 {b} 的引线交叉")
        if problems:
            self._warned = True
            more = f" 等 {len(problems)} 处" if len(problems) > 3 else ""
            warnings.warn(f"引线标注：{'；'.join(problems[:3])}{more}。"
                          f"用 layout.swap / move / edit 调开（debug=True 可以看坐标）", stacklevel=2)

    def _draw_debug(self, renderer) -> None:
        """在拐点、终点（以及单给的起点）旁写上经纬度，坐标文字朝地图那边写，带白边。"""
        to_px, ident = self.axes.transData.transform, IdentityTransform()
        halo = [patheffects.withStroke(linewidth=2, foreground="white")]
        for n, (side, start, elbow, end, explicit) in self._data.items():
            inward = "left" if side == "left" else "right"             # 左列往右写、右列往左写，都朝地图
            pts = [("拐", elbow, "s", inward, "bottom"), ("终", end, "o", "left", "bottom")]
            if explicit:
                pts.append(("起", start, "|", inward, "top"))                # 起点写在线下方
            for tag, p, mk, ha, va in pts:
                x, y = to_px(p)
                dx, dy = (3 if ha == "left" else -3), (3 if va == "bottom" else -3)
                for a in (Line2D([x], [y], marker=mk, ms=4, mfc="none", mec=self._debug_color, mew=0.8,
                                 transform=ident, clip_on=False),
                          Text(x + dx, y + dy, f"{tag} {p[0]:.4f}, {p[1]:.4f}", fontsize=5.5, ha=ha, va=va,
                               color=self._debug_color, transform=ident, clip_on=False, path_effects=halo)):
                    a.set_figure(self.figure)
                    a.draw(renderer)

    @allow_rasterization
    def draw(self, renderer) -> None:
        if not self.get_visible():
            return
        self._layout(renderer)
        self._check(renderer)
        for a in self._children():                                       # 只画排上了的（参数包里删掉的名字不画）
            a.draw(renderer)
        if self._debug:
            self._draw_debug(renderer)
        self.stale = False

    def get_window_extent(self, renderer=None) -> Bbox:
        renderer = renderer or self.figure._get_renderer()             # 与 matplotlib 自己的 Text 同一做法
        self._layout(renderer)
        boxes = [b for n in self._data if (b := self._label_box(n, renderer)) is not None]
        boxes += [self.lines[n].get_window_extent(renderer) for n in self._data if self.lines[n].get_visible()]
        return Bbox.union(boxes) if boxes else Bbox.null()

    def get_tightbbox(self, renderer=None) -> Bbox:
        return self.get_window_extent(renderer)


class RegionTexts(Artist):
    """区内标注：名字和数值直接写在每个区的落点上（区内离边界最远的点），由 Regions.text() 创建并加到 ax 上。

    co.texts[名字] 名字（Text）、co.nums[名字] 数值（Text），都是 matplotlib 对象，可以接着改。
    co.overflow：最近一次绘制时文字超出所在区的名字（小区放不下时），可以拿去 geo.label(ax, ..., ) 引到外面；
    overflow="hide" 时这些名字不画，"show" 照画并警告一次。
    位置每次绘制按当时的像素算，缩放、存 300 dpi 都不会错位。
    """

    def __init__(self, ax, items: Mapping[str, tuple[str, float | None]], anchors: Mapping[str, np.ndarray],
                 contains: Callable, *, props: Mapping | None = None, each: Mapping | None = None, hot=(),
                 fmt: str | Callable = "{:,.0f}", fs: float = 9, stack: bool = True, sep: float = 1,
                 halo=True, overflow: str = "show"):
        super().__init__()
        if overflow not in ("show", "hide"):
            raise ValueError(f"overflow 只能是 'show' 或 'hide'，拿到 {overflow!r}")
        self.axes = ax
        self.set_figure(ax.figure)
        self.set_clip_on(False)
        self.set_zorder(6)                           # 压在引线（5）上面：白边把穿过的引线遮住，字不被线划过
        self._anchors = {n: np.asarray(anchors[n], float) for n in items}
        self._contains, self._stack, self._sep, self._overflow_mode = contains, stack, float(sep), overflow
        self.overflow: list[str] = []
        self._warned = False
        halo = "white" if halo is True else halo
        fx = {"path_effects": [patheffects.withStroke(linewidth=2.2, foreground=halo)]} if halo else {}
        styles = _part_styles(items, props, each, hot, fs, extra={"name": fx, "value": fx} if fx else None)
        self.texts: dict[str, Text] = {}
        self.nums: dict[str, Text] = {}
        ident = IdentityTransform()
        for n, (label, value) in items.items():
            self.texts[n] = Callouts._make(self, Text(0, 0, label), styles[n]["name"], n, "name",
                                           transform=ident, clip_on=False)
            if value is not None:
                self.nums[n] = Callouts._make(self, Text(0, 0, _fmt_value(fmt, value)), styles[n]["value"], n,
                                              "value", transform=ident, clip_on=False)

    def _parts(self, n: str) -> list[Text]:
        return [t for t in (self.texts[n], self.nums.get(n)) if t is not None and t.get_visible() and t.get_text()]

    def _place(self, n: str, renderer) -> Bbox | None:
        """把名字、数值摆到落点上，返回整块文字的范围（像素）。上下两行（stack）或一行"名字 数值"。"""
        x, y = self.axes.transData.transform(self._anchors[n])
        parts, px = self._parts(n), renderer.points_to_pixels
        for t in (self.texts[n], self.nums.get(n)):
            if t is not None:
                t.set_position((x, y))
        if not parts:
            return None
        if len(parts) == 1:
            parts[0].set(ha="center", va="center", position=(x, y))
        elif self._stack:                                               # 名字在上、数值在下，整块中心对准落点
            name, num = parts
            hn, hv = (t.get_window_extent(renderer).height for t in parts)
            g = px(self._sep)
            top = y + (hn + g + hv) / 2
            name.set(ha="center", va="top", position=(x, top))
            num.set(ha="center", va="top", position=(x, top - hn - g))
        else:                                                           # 一行，共用基线
            big = max(parts, key=lambda t: t.get_fontsize())
            big.set(ha="left", va="baseline", position=(0, 0))
            ext = big.get_window_extent(renderer)
            ws = []
            for t in parts:
                t.set(ha="left", va="baseline")
                ws.append(t.get_window_extent(renderer).width)
            g = px(self._sep) * 3
            cx, yb = x - (sum(ws) + g * (len(ws) - 1)) / 2, y - (ext.y0 + ext.y1) / 2
            for t, w in zip(parts, ws):
                t.set_position((cx, yb))
                cx += w + g
        return Bbox.union([t.get_window_extent(renderer) for t in parts])

    def fits(self, n: str, renderer) -> bool:
        """n 的文字整块落在自己的区里吗（按当前版面）。"""
        b = self._place(n, renderer)
        if b is None:
            return True
        xs, ys = (b.x0, (b.x0 + b.x1) / 2, b.x1), (b.y0, (b.y0 + b.y1) / 2, b.y1)
        pts = self.axes.transData.inverted().transform([(x, y) for x in xs for y in ys if (x, y) != (xs[1], ys[1])])
        return bool(np.all(self._contains(n, pts)))

    def _shown(self, renderer) -> list[str]:
        self.overflow = [n for n in self.texts if not self.fits(n, renderer)]
        return [n for n in self.texts if self._overflow_mode == "show" or n not in self.overflow]

    @allow_rasterization
    def draw(self, renderer) -> None:
        if not self.get_visible():
            return
        shown = self._shown(renderer)
        if self.overflow and self._overflow_mode == "show" and not self._warned:
            self._warned = True
            warnings.warn(f"区内标注：这些区放不下文字，已压到区外：{self.overflow}。"
                          f"可以 geo.label(..., inside=\"auto\") 让放不下的自动引到外面", stacklevel=2)
        for n in shown:
            self._place(n, renderer)
            for t in self._parts(n):
                t.draw(renderer)
        self.stale = False

    def get_window_extent(self, renderer=None) -> Bbox:
        renderer = renderer or self.figure._get_renderer()
        boxes = [b for n in self._shown(renderer) if (b := self._place(n, renderer)) is not None]
        return Bbox.union(boxes) if boxes else Bbox.null()

    def get_tightbbox(self, renderer=None) -> Bbox:
        return self.get_window_extent(renderer)


if __name__ == '__main__':
    pass
