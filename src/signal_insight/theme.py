#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : theme.py
# @Path       : signal-insight/src/signal_insight/theme.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-10 16:30:00
# @Version    : v1.0.0
# @Description: 可视化主题：一个主题 = 一组语义色 + 分类色板 + 连续/发散色图 + 字体 + rcParams 补丁。
#               本模块只管“主题是什么、怎么注册/查找/加载”，不碰具体业务图，
#               业务里的语义映射（区域、客群 → 颜色角色）放在 viz.py。
# @ChangeLog:
#   2026-10-10 16:30:00 | Matri | v1.0.0 | 初始化创建：default / academic / business 三套内置主题

"""
扩展主题的三种方式（由轻到重）：

1. 基于已有主题派生（代码里）::

       from signal_insight.theme import get_theme, register_theme
       register_theme(get_theme("business").derive("acme", main="#E60012"))

2. 写一个 TOML 文件放进项目根的 ``themes/`` 目录，viz 导入时自动注册::

    name = "acme"
    base = "business"          # 只写和 base 不同的字段
    main = "#E60012"
    categorical = ["#E60012", "#1F2937", "#F59E0B", "#10B981", "#6366F1", "#06B6D4"]
    [rc]
    "lines.linewidth" = 2.2

3. 直接构造 ``Theme(...)`` 再 ``register_theme``。
"""
from __future__ import annotations

import re
import tomllib
import warnings
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Mapping

import matplotlib as mpl
from cycler import cycler
from matplotlib.colors import Colormap, LinearSegmentedColormap

__all__ = [
    "Theme", "register_theme", "get_theme", "available_themes",
    "theme_from_dict", "load_theme", "discover_themes",
    "DEFAULT", "ACADEMIC", "BUSINESS",
]

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# 语义色字段：viz 里的 MAIN / RED 等模块常量就是从这些字段同步出来的
COLOR_ROLES = (
    "main", "main_dark", "main_mid", "main_light",
    "gray", "gray_dark", "alert", "warn",
    "ink", "muted", "faint",
    "background", "grid", "edge", "tick",
)


@dataclass(frozen=True)
class Theme:
    """一套完整的配色/排版方案。字段都有默认值（= 原来的项目配色），派生时只改需要改的。"""

    name: str
    description: str = ""

    # —— 语义色：一种颜色只表达一件事 ——
    main: str = "#1D6FA5"          # 主色：强调“这张图要说的那件事”
    main_dark: str = "#174E73"
    main_mid: str = "#7FB3D9"
    main_light: str = "#DCEAF5"
    gray: str = "#C4CAD3"          # 打底/背景数据/“不明”
    gray_dark: str = "#8E99A6"
    alert: str = "#D64545"         # 只表示警示（原 RED）
    warn: str = "#B7791F"          # 次级提醒（原 AMBER）
    ink: str = "#1F2937"           # 标题
    muted: str = "#6B7280"         # 副标题
    faint: str = "#9CA3AF"         # 来源行

    # —— 画布 ——
    background: str = "#FFFFFF"
    grid: str = "#E5E7EB"
    edge: str = "#9CA3AF"
    tick: str = "#4B5563"

    # —— 色板 ——
    # 分类色：第 0 个建议就是 main；不同类别之间要能区分，且避免和 alert 混淆
    categorical: tuple[str, ...] = (
        "#1D6FA5", "#D9822B", "#3B8C66", "#7A5EA8", "#B04A6A", "#6B7F2A",
    )
    # 连续/发散色图：可以是一串色（浅→深 / 负→中→正），也可以是 matplotlib 已有色图名
    sequential: tuple[str, ...] | str = (
        "#F1F6FB", "#DCEAF5", "#7FB3D9", "#1D6FA5", "#174E73",
    )
    diverging: tuple[str, ...] | str = (
        "#D9822B", "#F2CDA6", "#F3F4F6", "#7FB3D9", "#174E73",
    )

    # —— 字体与标题区 ——
    fonts: tuple[str, ...] = ("TeX Gyre Termes", "Noto Serif CJK SC")
    title_size: float = 16
    subtitle_size: float = 10.5
    source_size: float = 8.5
    accent_bar: bool = True        # finish() 标题上方的主色小色条

    # —— 最后覆盖的 rcParams 补丁：主题风格差异（边框、刻度方向、线宽……）写这里 ——
    rc: Mapping[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        # TOML/JSON 里读出来的是 list，这里统一转成 tuple，保证主题不可变
        for name in ("categorical", "fonts", "sequential", "diverging"):
            value = getattr(self, name)
            if isinstance(value, list):
                object.__setattr__(self, name, tuple(value))
        object.__setattr__(self, "rc", dict(self.rc))
        self._validate()

    def _validate(self) -> None:
        bad = [r for r in COLOR_ROLES if not _HEX.match(getattr(self, r))]
        bad += [f"categorical[{i}]" for i, c in enumerate(self.categorical) if not _HEX.match(c)]
        for kind in ("sequential", "diverging"):
            value = getattr(self, kind)
            if isinstance(value, str):
                if value not in mpl.colormaps:
                    bad.append(f"{kind}={value!r}(不是已注册的色图)")
            else:
                if len(value) < 2:
                    bad.append(f"{kind}(至少 2 个颜色)")
                bad += [f"{kind}[{i}]" for i, c in enumerate(value) if not _HEX.match(c)]
        if not self.categorical:
            bad.append("categorical(不能为空)")
        if not self.fonts:
            bad.append("fonts(不能为空)")
        if bad:
            raise ValueError(f"主题 {self.name!r} 的配置不合法：{', '.join(bad)}")

    # ------------------------------------------------------------------ #
    def derive(self, name: str, **changes: Any) -> "Theme":
        """以当前主题为底派生新主题；rc 是合并而不是整体替换。"""
        if "rc" in changes:
            changes["rc"] = {**self.rc, **changes["rc"]}
        return replace(self, name=name, **changes)

    def color(self, index: int) -> str:
        """第 index 个分类色（超出长度循环使用）。"""
        return self.categorical[index % len(self.categorical)]

    def resolve(self, role: str) -> str:
        """把“颜色角色”解析成色值：'main' / 'gray' 等语义名，或 'cat:N' 表示第 N 个分类色，或直接写 '#RRGGBB'。"""
        if role.startswith("#"):
            return role
        if role.startswith("cat:"):
            return self.color(int(role[4:]))
        if role in COLOR_ROLES:
            return getattr(self, role)
        raise KeyError(f"未知颜色角色 {role!r}，可用：{', '.join(COLOR_ROLES)} 或 'cat:N'")

    def cmap(self, kind: str = "sequential") -> Colormap:
        """返回主题的连续 ('sequential') 或发散 ('diverging') 色图。"""
        if kind not in ("sequential", "diverging"):
            raise ValueError("kind 只能是 'sequential' 或 'diverging'")
        spec = getattr(self, kind)
        if isinstance(spec, str):
            return mpl.colormaps[spec]
        return LinearSegmentedColormap.from_list(f"{self.name}.{kind}", list(spec))

    def cmap_name(self, kind: str = "sequential") -> str:
        spec = getattr(self, kind)
        return spec if isinstance(spec, str) else f"{self.name}.{kind}"

    def register_cmaps(self) -> None:
        """把主题色图注册进 matplotlib，之后可以 cmap='business.sequential' 这样按名使用。"""
        for kind in ("sequential", "diverging"):
            if isinstance(getattr(self, kind), str):
                continue
            name = self.cmap_name(kind)
            if name in mpl.colormaps:  # 反复切换主题时先注销，避免 matplotlib 的覆盖告警
                mpl.colormaps.unregister(name)
            mpl.colormaps.register(self.cmap(kind), name=name)

    def rc_params(self) -> dict[str, Any]:
        """主题对应的完整 rcParams（公共骨架 + 主题自己的 rc 补丁）。"""
        params: dict[str, Any] = {
            "font.family": list(self.fonts), "axes.unicode_minus": True,
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": True, "axes.grid.axis": "y",
            "axes.axisbelow": True, "grid.color": self.grid,
            "axes.edgecolor": self.edge,
            "axes.labelcolor": self.ink, "axes.titlecolor": self.ink,
            "text.color": self.ink,
            "xtick.color": self.tick, "ytick.color": self.tick,
            "xtick.major.size": 0, "ytick.major.size": 0,
            "legend.frameon": False,
            "figure.facecolor": self.background, "axes.facecolor": self.background,
            "savefig.facecolor": self.background,
            "axes.prop_cycle": cycler(color=list(self.categorical)),
            "image.cmap": self.cmap_name("sequential"),
            "figure.dpi": 100, "savefig.dpi": 300,
        }
        params.update(self.rc)
        return params


# ====================================================================== #
# 内置主题
# ====================================================================== #

# 原来的项目配色，一个像素都不变（只是多了分类色循环和色图）
DEFAULT = Theme(
    name="default",
    description="项目原配色：灰色打底、蓝色强调、红色只表示警示",
)

# 学术规范：色盲友好（Okabe-Ito，去掉了和警示红冲突的朱红）、衬线字体、
# 四面边框 + 内向刻度、无网格，适合论文/报告插图，黑白打印也能分清明暗
ACADEMIC = DEFAULT.derive(
    "academic",
    description="学术规范：Okabe-Ito 色盲友好色板，衬线字体，完整边框与内向刻度",
    main="#0072B2", main_dark="#004C77", main_mid="#56B4E9", main_light="#D6EAF5",
    gray="#BDBDBD", gray_dark="#7F7F7F",
    alert="#D55E00", warn="#E69F00",
    ink="#000000", muted="#404040", faint="#7F7F7F",
    grid="#E0E0E0", edge="#000000", tick="#000000",
    categorical=("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#000000"),
    sequential="cividis",          # 感知均匀、色盲友好、灰度打印单调
    diverging="PuOr",
    fonts=("TeX Gyre Termes", "Noto Serif CJK SC"),
    title_size=13, subtitle_size=10, source_size=8,
    accent_bar=False,
    rc={
        "axes.spines.top": True, "axes.spines.right": True, "axes.spines.left": True,
        "axes.linewidth": 0.8, "axes.grid": False,
        "xtick.direction": "in", "ytick.direction": "in",
        "xtick.top": True, "ytick.right": True,
        "xtick.major.size": 3.5, "ytick.major.size": 3.5,
        "xtick.major.width": 0.8, "ytick.major.width": 0.8,
        "lines.linewidth": 1.5, "lines.markersize": 5,
        "mathtext.fontset": "stix",  # 公式字体与 Termes(Times) 一致
        "legend.fontsize": 9,
    },
)

# 商业规范：饱和度更高、色相拉开的活泼色板，无衬线字体，线条更粗，
# 依然保留“灰色打底、红色只表示警示”的纪律
BUSINESS = DEFAULT.derive(
    "business",
    description="商业规范：明快活泼的品牌色板，无衬线字体，适合汇报/看板",
    main="#2563EB", main_dark="#1E40AF", main_mid="#93B4F5", main_light="#E3ECFD",
    gray="#CBD2DC", gray_dark="#8A94A6",
    alert="#E5484D", warn="#D97706",
    ink="#111827", muted="#5B6475", faint="#9AA3B2",
    grid="#EEF1F5", edge="#CBD2DC", tick="#5B6475",
    categorical=("#2563EB", "#FF7A45", "#10B981", "#8B5CF6", "#06B6D4", "#EAB308"),
    sequential=("#EFF5FF", "#BFD4FB", "#7FA6F5", "#3B73EA", "#1E40AF"),
    diverging=("#C2410C", "#FDBA8C", "#F5F6F8", "#93B4F5", "#1E40AF"),
    fonts=("TeX Gyre Termes", "Noto Serif CJK SC"),
    title_size=17, subtitle_size=11, source_size=8.5,
    accent_bar=True,
    rc={
        "lines.linewidth": 2.2, "lines.solid_capstyle": "round",
        "axes.titleweight": "bold",
    },
)


# ====================================================================== #
# 注册表
# ====================================================================== #
_REGISTRY: dict[str, Theme] = {}


def register_theme(theme: Theme, *, overwrite: bool = False) -> Theme:
    """注册主题。默认不允许同名覆盖，防止误改内置主题；企业要整体替换时显式 overwrite=True。"""
    if theme.name in _REGISTRY and not overwrite:
        raise ValueError(f"主题 {theme.name!r} 已存在，如确需覆盖请传 overwrite=True")
    _REGISTRY[theme.name] = theme
    return theme


def get_theme(theme: str | Theme) -> Theme:
    """按名字取主题；传入的已经是 Theme 则原样返回（方便函数参数两种都收）。"""
    if isinstance(theme, Theme):
        return theme
    try:
        return _REGISTRY[theme]
    except KeyError:
        raise KeyError(f"没有名为 {theme!r} 的主题，可用：{', '.join(available_themes())}") from None


def available_themes() -> list[str]:
    return list(_REGISTRY)


for _t in (DEFAULT, ACADEMIC, BUSINESS):
    register_theme(_t)


# ====================================================================== #
# 从配置文件加载
# ====================================================================== #
_FIELD_NAMES = {f.name for f in fields(Theme)}


def theme_from_dict(data: Mapping[str, Any]) -> Theme:
    """从字典构造主题，支持 base 继承：只需写与 base 不同的字段。"""
    data = dict(data)
    name = data.pop("name", None)
    if not name:
        raise ValueError("主题配置缺少 name")
    base = get_theme(data.pop("base", "default"))
    unknown = set(data) - _FIELD_NAMES
    if unknown:
        raise ValueError(f"主题 {name!r} 含未知字段：{', '.join(sorted(unknown))}")
    return base.derive(name, **data)


def load_theme(path: str | Path, *, register: bool = True, overwrite: bool = False) -> Theme:
    """读取一个 TOML 主题文件。"""
    with open(path, "rb") as f:
        theme = theme_from_dict(tomllib.load(f))
    if register:
        register_theme(theme, overwrite=overwrite)
    return theme


def discover_themes(directory: str | Path) -> list[Theme]:
    """加载目录下所有 *.toml 主题（按文件名排序，便于用 base 互相继承）。

    单个文件出错只告警不中断，避免一个写错的主题拖垮所有出图。
    同名会覆盖——这样企业可以放一个 business.toml 来微调内置的商业主题。
    """
    directory = Path(directory)
    loaded: list[Theme] = []
    if not directory.is_dir():
        return loaded
    for file in sorted(directory.glob("*.toml")):
        try:
            loaded.append(load_theme(file, overwrite=True))
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"主题文件 {file.name} 加载失败，已跳过：{exc}", stacklevel=2)
    return loaded
