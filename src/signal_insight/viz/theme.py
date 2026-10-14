#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : viz.py
# @Path       : signal-insight/src/signal_insight/viz.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-10 15:00:28
# @Version    : v1.3.0
# @Description: 统一出图风格：主题切换、业务语义配色、标题区/来源行
# @ChangeLog:
#   2026-10-10 15:00:28 | Matri | v1.0.0 | 初始化创建
#   2026-10-10 16:30:00 | Matri | v1.1.0 | 接入主题系统(theme.py)：default/academic/business 可切换，
#                                          旧常量 MAIN/RED/AREA_COLOR 等保持可用并随主题同步
#   2026-10-10 18:00:00 | Matri | v1.2.0 | apply_theme 返回本机实际生效字体并在缺中文字体时提示；新增 GREEN(通过)
#   2026-10-10 20:00:00 | Matri | v1.3.0 | 切换主题时同步重绑 `from viz import MAIN` 等已导入的颜色常量，
#                                          旧代码 color=MAIN 不用改成 viz.MAIN；颜色常量加入 __all__

"""图表主题：语义色、切换主题、标题区与来源行。

只会因为"图表规范变了"而改（AGENTS.md 第 2 条）。分工：
  · 外观（字体、坐标轴、网格、默认循环色、标题字号）写在 styles/*.mplstyle，用 matplotlib 自带的 plt.style 加载；
  · 含义（MAIN 强调、RED 只表示警示、"不明"永远是灰色）写在本文件的常量里，不随主题变；
  · finish() 统一标题区、来源行和保存。

import 本模块不改任何全局设置、不读文件（AGENTS.md 第 7 条）：要生效，调用方显式调用 apply_theme()。
"""
from __future__ import annotations

from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Iterator

import matplotlib.pyplot as plt
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.patches import Rectangle

from .. import config

__all__ = [
    "MAIN", "MAIN_LIGHT", "MAIN_DARK", "MAIN_MID", "GRAY", "GRAY_DARK",
    "RED", "AMBER", "GREEN", "INK", "MUTED", "FAINT",
    "AREAS", "AREA_COLOR", "SEG_COLOR", "FONTS",
    "apply_theme", "use_theme", "available_themes", "finish", "margins_in",
]

# ── 语义色：灰色打底，一种颜色强调一件事，红色只表示警示 ──
# 这些是"含义"，不是"外观"：换主题不换它们，所以 from ... import MAIN 拿到的值永远对。
MAIN, MAIN_LIGHT, MAIN_DARK, MAIN_MID = "#1D6FA5", "#DCEAF5", "#174E73", "#7FB3D9"
GRAY, GRAY_DARK = "#C4CAD3", "#8E99A6"
RED, AMBER, GREEN = "#D64545", "#B7791F", "#3B8C66"     # 不通过 / 警告 / 通过
INK, MUTED, FAINT = "#1F2937", "#6B7280", "#9CA3AF"      # 标题与正文 / 副标题 / 来源行

# 同一个区域、同一类客群，在所有图里颜色相同
AREAS = ("西塔", "太原街商圈", "中街商圈", "沈阳北站", "沈阳世博园", "棋盘山风景区")
AREA_COLOR = dict(zip(AREAS, ["#1D6FA5", "#D9822B", "#3B8C66", "#7A5EA8", "#B04A6A", "#6B7F2A"]))
SEG_COLOR = {"市内来访": MAIN, "周边居民": MAIN_MID, "外地来客": "#D9822B", "市外来访": "#D9822B",
            "过夜地不明": GRAY}                           # "不明"永远是灰色：不是一类人，是不知道

FONTS: list[str] = []                                    # apply_theme() 之后 = 当前生效的 font.family

# ── 主题文件 ──
_STYLES = files(__package__) / "styles"                  # 随包安装的 styles/ 文件夹
_BASE = f"{__package__}.styles.base"


def available_themes() -> list[str]:
    """内置主题名（styles/ 里除 base 以外的 .mplstyle）。"""
    return sorted(p.name.removesuffix(".mplstyle") for p in _STYLES.iterdir()
                if p.name.endswith(".mplstyle") and p.name != "base.mplstyle")

def _resolve(theme) -> str:
    """主题名 → plt.style 能认的写法。内置名用包内路径；也可以直接给一个 .mplstyle 文件路径。"""
    name = str(theme or config.THEME)
    if (_STYLES / f"{name}.mplstyle").is_file():
        return f"{__package__}.styles.{name}"
    if name.endswith(".mplstyle") and Path(name).is_file():
        return name
    raise ValueError(f"没有主题 {name!r}：可用 {', '.join(available_themes())}，或给一个 .mplstyle 文件路径")

def apply_theme(theme: str | Path | None = None) -> list[str]:
    """应用主题，返回生效的字体列表。每本 notebook 第一格调用一次。

    theme 不给就用 config.THEME（环境变量 SIGNAL_THEME 可覆盖）。
    总是先套 base 再套主题：切换顺序不影响结果，不会残留上一个主题的设置。
    """
    plt.style.use([_BASE, _resolve(theme)])
    FONTS[:] = plt.rcParams["font.family"]               # 原地更新：from ... import FONTS 也跟着变
    return list(FONTS)


@contextmanager
def use_theme(theme: str | Path) -> Iterator[list[str]]:
    """临时换主题，出了 with 自动恢复。同一本 notebook 里出两版图时用::

        with viz.use_theme("academic"):
            fig, ax = plt.subplots()
            ...
            viz.finish(fig, title, subtitle, SOURCE, "paper/fig1.pdf", accent=False)

    建图、画图、finish 都要写在 with 里面：已经画好的图不会因为换主题重新着色。
    """
    with plt.style.context([_BASE, _resolve(theme)]):
        yield list(plt.rcParams["font.family"])


# ── 标题区与来源行 ──
# 按"英寸"留白而不是按比例：图高 4 英寸还是 7 英寸，标题区看起来一样大。
# DistrictMap.figure() 也用 margins_in() 算图高，两边的数字只有这一处。
def margins_in(n_sub: int) -> tuple[float, float]:
    """(顶部标题区高度, 底部来源行高度)，单位英寸；n_sub 是副标题行数。"""
    return 0.67 + 0.23 * n_sub, 0.32


def finish(fig, title: str, subtitle: str, source: str, path: str | Path | None = None,
           *, accent: bool = True) -> Path | None:
    """给一张图加统一的标题区和来源行，留好上下空白；给了 path 就保存（相对路径存进 image/），返回完整路径。

    标题是 fig.texts[0]："读回断言"靠它检查标题里的数字是不是代码算的。
    标题字号取 rcParams["figure.titlesize"]，所以主题文件能改它。accent=False 去掉标题上方的主色短条（论文插图用）。
    不做的事：不读数据库，不算业务数字（标题里的数由调用方算好传进来）。
    """
    h, w = fig.get_figheight(), fig.get_figwidth()
    n_sub = subtitle.count("\n") + 1 if subtitle else 0
    if accent:
        fig.add_artist(Rectangle((0.02, 1 - 0.115 / h), 0.38 / w, 0.045 / h,
                                transform=fig.transFigure, color=MAIN, lw=0))
    fig.text(0.02, 1 - 0.19 / h, title, fontsize=plt.rcParams["figure.titlesize"],
            fontweight=plt.rcParams["figure.titleweight"], color=INK, va="top")
    if subtitle:
        fig.text(0.02, 1 - 0.48 / h, subtitle, fontsize=10.5, color=MUTED, va="top", linespacing=1.5)
    fig.text(0.02, 0.1 / h, source, fontsize=8.5, color=FAINT)

    head, foot = margins_in(n_sub)
    top, bottom = 1 - head / h, foot / h
    engine = fig.get_layout_engine()
    if isinstance(engine, ConstrainedLayoutEngine):
        engine.set(rect=(0.01, bottom, 0.98, top - bottom))     # 注意：这里是 (左, 下, 宽, 高)
    else:
        fig.tight_layout(rect=(0.01, bottom, 0.99, top))        # 这里是 (左, 下, 右, 上)

    if path is None:
        return None
    out = Path(path) if Path(path).is_absolute() else config.IMAGE_DIR / path
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    return out
