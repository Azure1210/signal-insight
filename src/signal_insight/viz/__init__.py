#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : __init__.py.py
# @Path       : signal-insight/src/signal_insight/viz/__init__.py.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-14 08:31:17
# @Version    : v1.0.0
# @Description: 
# @ChangeLog:
#   2026-10-14 08:31:17 | Matri | v1.0.0 | 初始化创建
"""图表：theme 管主题（语义色、切换主题、标题区），maps 管地图，styles/ 放主题文件。

D02 时这里是 viz.py + theme.py 两个文件；D04 主题改用 .mplstyle 文件，
数据文件只能跟着"包"一起安装，于是 viz 变成了文件夹。下面这行"重新导出"保证原来的写法一行都不用改：
    from signal_insight import viz;  viz.finish(...)、viz.apply_theme("business")   照样能用
    from signal_insight.viz import MAIN, GRAY                                       照样能用
"""
from .theme import *          # noqa: F401,F403  （theme.py 的 __all__ 决定导出哪些名字）
from .theme import __all__ as _theme_all
from . import maps            # noqa: F401  地图用 viz.maps.xxx 调用

__all__ = [*_theme_all, "maps"]

# D02 主题引擎里的这些名字 D04 删掉了。直接报 AttributeError 看不出原因，这里给一句迁移提示。
_REMOVED = {
    "Theme": "主题现在是 styles/ 里的 .mplstyle 文件，没有 Theme 类了",
    "get_theme": "用 viz.available_themes() 查看有哪些主题",
    "register_theme": "新主题 = 写一个 .mplstyle 文件，用 viz.apply_theme(文件路径) 加载",
    "current_theme": "当前外观就是 plt.rcParams；语义色是固定常量",
}


def __getattr__(name):
    if name in _REMOVED:
        raise AttributeError(f"viz.{name} 已在 D04 移除：{_REMOVED[name]}")
    raise AttributeError(f"module 'signal_insight.viz' has no attribute {name!r}")


if __name__ == '__main__':
    pass
