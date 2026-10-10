#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : viz.py
# @Path       : signal-insight/src/signal_insight/viz.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-10 15:00:28
# @Version    : v1.1.0
# @Description: 统一出图风格：主题切换、业务语义配色、标题区/来源行
# @ChangeLog:
#   2026-10-10 15:00:28 | Matri | v1.0.0 | 初始化创建
#   2026-10-10 16:30:00 | Matri | v1.1.0 | 接入主题系统(theme.py)：default/academic/business 可切换，
#                                          旧常量 MAIN/RED/AREA_COLOR 等保持可用并随主题同步

# 配色纪律（所有主题共同遵守）：灰色打底，一种颜色强调一件事，红色只表示警示
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import matplotlib.pyplot as plt
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.patches import Rectangle

from signal_insight import config
from signal_insight.theme import (
    Theme, available_themes, discover_themes, get_theme, register_theme,
)

__all__ = [
    "apply_theme", "use_theme", "current_theme", "available_themes",
    "register_theme", "get_theme", "Theme", "finish",
    "AREA_COLOR", "SEG_COLOR", "AREAS",
]

# ---------------------------------------------------------------------- #
# 业务语义 → 颜色角色。这里只说“谁用哪个角色”，具体色值由当前主题决定，
# 所以换主题时“同一区域在所有图里同色”这条规则依然成立。
# 角色写法见 Theme.resolve：语义名 'main'/'gray'...，或 'cat:N' 第 N 个分类色。
# 新增区域/客群：往下面加一行即可。
# ---------------------------------------------------------------------- #
AREAS = ("西塔", "太原街商圈", "中街商圈", "沈阳北站", "沈阳世博园", "棋盘山风景区")
AREA_ROLE: dict[str, str] = {area: f"cat:{i}" for i, area in enumerate(AREAS)}

SEG_ROLE: dict[str, str] = {
    "市内来访": "main", "周边居民": "main_mid",
    "外地来客": "cat:1", "市外来访": "cat:1",
    "过夜地不明": "gray",       # “不明”永远是灰色：不是一类人，是不知道
}

# 以下模块常量保留旧名字，兼容已有代码；它们会在切换主题时被同步。
# 注意：`from viz import MAIN` 拿到的是导入那一刻的值，切主题后不会变，
# 推荐写 `viz.MAIN` 或 `viz.current_theme().main`。
# AREA_COLOR / SEG_COLOR 是原地更新的同一个 dict，两种导入方式都安全。
MAIN = MAIN_LIGHT = GRAY = RED = ""
INK = MUTED = FAINT = ""
MAIN_DARK = MAIN_MID = GRAY_DARK = AMBER = ""
FONTS: list[str] = []
AREA_COLOR: dict[str, str] = {}
SEG_COLOR: dict[str, str] = {}

_LEGACY = {
    "MAIN": "main", "MAIN_LIGHT": "main_light", "MAIN_DARK": "main_dark",
    "MAIN_MID": "main_mid", "GRAY": "gray", "GRAY_DARK": "gray_dark",
    "RED": "alert", "AMBER": "warn", "INK": "ink", "MUTED": "muted", "FAINT": "faint",
}

_current: Theme = get_theme("default")


def _activate(theme: Theme) -> None:
    """把主题同步到模块常量与语义映射（不改 rcParams）。"""
    global _current, FONTS
    _current = theme
    g = globals()
    for const, role in _LEGACY.items():
        g[const] = getattr(theme, role)
    FONTS = list(theme.fonts)
    AREA_COLOR.clear()
    AREA_COLOR.update({k: theme.resolve(r) for k, r in AREA_ROLE.items()})
    SEG_COLOR.clear()
    SEG_COLOR.update({k: theme.resolve(r) for k, r in SEG_ROLE.items()})


def current_theme() -> Theme:
    return _current


def apply_theme(theme: str | Theme | None = None) -> list[str]:
    """应用主题：更新 matplotlib rcParams、注册主题色图、同步模块常量。

    theme 可以是主题名（'default' / 'academic' / 'business' / 自定义）或 Theme 对象；
    不传则用 config.THEME（可被环境变量 SIGNAL_THEME 覆盖）。
    返回字体列表（与旧版返回值保持一致）。
    """
    t = get_theme(theme if theme is not None else config.THEME)
    t.register_cmaps()
    plt.rcParams.update(t.rc_params())  # type: ignore[arg-type]  # matplotlib 对 update 键名标注过严，这里键都是合法 rcParams 名
    _activate(t)
    return list(t.fonts)


@contextmanager
def use_theme(theme: str | Theme) -> Iterator[Theme]:
    """临时切换主题，退出 with 后 rcParams 和模块常量都恢复，适合同一 notebook 里出两版图::

        with viz.use_theme("academic") as t:
            fig, ax = plt.subplots()
            ax.plot(x, y, color=t.main)
            viz.finish(fig, "标题", "副标题", config.SOURCE_NOTE, "paper/fig1.pdf")
    """
    previous = _current
    with plt.rc_context():
        apply_theme(theme)
        try:
            yield _current
        finally:
            _activate(previous)


def finish(fig, title: str, subtitle: str, source: str,
        path: str | None = None) -> Path | None:
    """给一张图添加统一的标题区和来源行，留好上下都空白：path给文件名时保存到 image/ 返回完整的路径"""
    t = _current
    h, w = fig.get_figheight(), fig.get_figwidth()
    n_sub = subtitle.count("\n") + 1 if subtitle else 0
    if t.accent_bar:
        fig.add_artist(Rectangle((0.02, 1 - 0.115 / h), 0.38 / w, 0.045 / h,
                                transform=fig.transFigure, color=t.main, lw=0))
    fig.text(0.02, 1 - 0.19 / h, title, fontsize=t.title_size,
            fontweight='bold', color=t.ink, va="top")
    if subtitle:
        fig.text(0.02, 1 - 0.48 / h, subtitle, fontsize=t.subtitle_size,
                color=t.muted, va='top', linespacing=1.5)
    fig.text(0.02, 0.1 / h, source, fontsize=t.source_size, color=t.faint)

    top, bottom = 1 - (0.67 + 0.23 * n_sub) / h, 0.32 / h  # 上留标题区，下面留来源行
    engine = fig.get_layout_engine()
    if isinstance(engine, ConstrainedLayoutEngine):
        engine.set(rect=(0.01, bottom, 0.99, top))
    else:
        fig.tight_layout(rect=(0.01, bottom, 0.99, top))

    if path is None:
        return None

    out = Path(path) if Path(path).is_absolute() else config.IMAGE_DIR / path
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches='tight')
    return out


# 导入时：加载项目 themes/ 目录下的自定义主题，并把常量同步到配置的主题（不动 rcParams，
# 和旧版一样，真正生效要调用 apply_theme()）
discover_themes(config.THEME_DIR)
_activate(get_theme(config.THEME))


if __name__ == '__main__':
    pass
