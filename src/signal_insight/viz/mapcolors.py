#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : mapcolors.py
# @Path       : signal-insight/src/signal_insight/viz/mapcolors.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-14 22:00:00
# @Version    : v1.3.0
# @Description: 地图自己的默认颜色，和 theme.py 无关
# @ChangeLog:
#   2026-10-14 22:00:00 | Matri | v1.0.0 | 初始化创建：地图颜色从 theme 里独立出来，可整体设置、临时设置、恢复默认
#   2026-10-15 10:00:00 | Matri | v1.1.0 | 新增 land（底图底色）
#   2026-10-15 20:00:00 | Matri | v1.2.0 | 新增 heat_low / heat_mid / heat_high（六边形热力色阶）、small（不足门槛的格子）
#   2026-10-16 10:00:00 | Matri | v1.3.0 | 新增 small_hatch（fill 小样本抑制的斜线颜色）

"""地图的默认颜色。maps.py 和 callouts.py 只从这里取默认色，不读 theme.py：
主题管通用图表的外观，地图的颜色单独设，改一边不会动另一边。

每个颜色都只是"没传参数时用什么"。任何一次调用传了 color= / lineprops= 之类，就以调用为准。

    viz.maps.colors                                   # 看当前设置（notebook 里显示色块）
    viz.maps.colors.set(hot="#D64545", high="#1D6FA5") # 整体改，之后画的地图都用它
    with viz.maps.colors.use(ink="#000000"):           # 临时改，出了 with 恢复
        geo.plot(values, texts=True)
    viz.maps.colors.reset()                            # 恢复默认

想和主题保持一致，就自己把主题的颜色填进来：viz.maps.colors.set(hot=viz.MAIN, ink=viz.INK)。
颜色在画的那一刻取定：先 set，再画。
"""
from __future__ import annotations

import html
from contextlib import contextmanager
from typing import Iterator

import matplotlib.colors as mcolors

__all__ = ["MapColors", "DEFAULTS", "colors"]

DEFAULTS: dict[str, str] = {
    "ink":    "#1F2937",   # 标注的名字和数值、外边界、落点、散点、比例尺、指北针
    "line":   "#6B7280",   # 引线
    "hot":    "#1D6FA5",   # 强调：hot 的名字和数值、edges 的整圈边界
    "land":   "#EEF0F3",   # 底图的底色（陆地）：没数据的区就是这个颜色，内边界白线压在上面才看得见
    "low":    "#FFFFFF",   # 填色色阶的浅端（最小值）
    "high":   "#8E99A6",   # 填色色阶的深端（最大值）
    "border": "#FFFFFF",   # 内边界（区与区之间）
    "nan":    "none",      # 数据层里没有数值、没给颜色的区（"none" = 不填，露出底图的 land）
    "debug":  "#B7791F",   # debug=True 时写的坐标
    "heat_low":  "#DCEAF5",   # 热力色阶（hexbin）：浅端，主色浅
    "heat_mid":  "#7FB3D9",   # 热力色阶：中段，主色中
    "heat_high": "#174E73",   # 热力色阶：深端，主色深
    "small":     "#D5DAE1",   # 不足门槛（<5 人）的格子 / 区域：hexbin(small="gray")、fill(small="gray")；比 land 深一档
    "small_hatch": "#9CA3AF", # fill(min_value=5) 默认把不足门槛的区画成白底斜线，这是斜线的颜色
}
_HELP = {"ink": "文字/外边界/落点/散点", "line": "引线", "hot": "强调", "land": "底图底色", "low": "色阶浅端", "high": "色阶深端",
         "border": "内边界", "nan": "无数值的区", "debug": "debug 坐标",
         "heat_low": "热力浅端", "heat_mid": "热力中段", "heat_high": "热力深端", "small": "不足门槛的格子", "small_hatch": "小样本斜线"}


class MapColors:
    """地图的默认颜色，按名字读：colors.ink、colors.hot……只读，改用 set / use / reset。"""
    __slots__ = ("_v",)

    def __init__(self) -> None:
        object.__setattr__(self, "_v", dict(DEFAULTS))

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._v[name]
        except KeyError:
            raise AttributeError(f"地图颜色没有 {name!r}；可用 {', '.join(DEFAULTS)}") from None

    def __setattr__(self, name, value):
        raise AttributeError(f"用 viz.maps.colors.set({name}=...) 改颜色")

    def __dir__(self):
        return list(DEFAULTS)

    @staticmethod
    def _check(kw: dict) -> dict:
        if bad := sorted(set(kw) - set(DEFAULTS)):
            raise TypeError(f"地图颜色没有 {bad}；可用 {', '.join(DEFAULTS)}")
        for k, v in kw.items():
            if not (isinstance(v, str) and v.lower() == "none") and not mcolors.is_color_like(v):
                raise ValueError(f"地图颜色 {k} 的值 {v!r} 不是颜色")
        return kw

    def set(self, **kw: str) -> "MapColors":
        """整体改几种颜色，之后画的地图都用它。返回自己。"""
        self._v.update(self._check(kw))
        return self

    def reset(self) -> "MapColors":
        """全部恢复默认。"""
        self._v.clear()
        self._v.update(DEFAULTS)
        return self

    @contextmanager
    def use(self, **kw: str) -> Iterator["MapColors"]:
        """临时改，出了 with 恢复。"""
        old = dict(self._v)
        self._v.update(self._check(kw))
        try:
            yield self
        finally:
            self._v.clear()
            self._v.update(old)

    def as_dict(self) -> dict[str, str]:
        return dict(self._v)

    def __repr__(self) -> str:
        return "地图颜色：" + "，".join(f"{k}={v}" for k, v in self._v.items())

    def _repr_html_(self) -> str:
        chip = ('<span style="display:inline-block;margin:2px 12px 2px 0;font:12px monospace">'
                '<span style="display:inline-block;width:14px;height:14px;vertical-align:middle;'
                'border:1px solid #0003;background:{c}"></span> {n}（{h}）{c}</span>')
        return "<div>" + "".join(chip.format(n=k, h=_HELP[k], c=html.escape(v)) for k, v in self._v.items()) + "</div>"


colors = MapColors()
