#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : demo.py
# @Path       : signal-insight/src/signal_insight/test/demo.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-14 11:13:05
# @Version    : v1.0.0
# @Description: 
# @ChangeLog:
#   2026-10-14 11:13:05 | Matri | v1.0.0 | 初始化创建
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DistrictMap 用法示例：一键默认 vs. 手动组合。

只用假的矩形边界（相邻区共用顶点，好让 _outline 只画外缘）。
真实项目里用 geo.rings_from_points 从数据库/geojson 还原。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # 无窗口环境也能跑
import matplotlib.pyplot as plt

# 若在项目里运行，把这两行换成：
#   from signal_insight.viz import maps, theme
# 下面把 maps/theme 简化成本地定义，方便你直接复制跑。
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from signal_insight.viz import maps, theme


# -------------------------------------------------------------- 假边界
def grid_districts(cols_x, rows_y, names):
    """把一个矩形网格切成区。相邻格共用顶点，_outline 就只描外缘。"""
    out = {}
    for j, name_row in enumerate(names):                    # j: 0 = 南
        for i, name in enumerate(name_row):
            x0, x1 = cols_x[i], cols_x[i + 1]
            y0, y1 = rows_y[j], rows_y[j + 1]
            out[name] = [np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])]
    return out


DISTRICTS = grid_districts(
    cols_x=[122.40, 122.75, 123.10, 123.50],
    rows_y=[41.35, 41.65, 41.95, 42.30],
    names=[
        ["辽中区", "铁西区", "苏家屯区"],       # 南
        ["新民市", "于洪区", "皇姑区"],         # 中
        ["法库县", "沈北新区", "沈河区"],       # 北
    ],
)


# -------------------------------------------------------------- 假数据
VALUES = {
    "辽中区":   820,
    "铁西区":   210,
    "苏家屯区":  35,
    "新民市":    14,
    "于洪区":    68,
    "皇姑区":    95,
    "法库县":     6,
    "沈北新区":  120,
    "沈河区":   340,
}
TEXTS = {n: f"{n}  {v}" for n, v in VALUES.items()}
HOT = ["辽中区", "沈河区"]

# 假站点：随机撒一些点
_rng = np.random.default_rng(7)
SITES = pd.DataFrame({
    "lng": _rng.uniform(122.45, 123.45, 600),
    "lat": _rng.uniform(41.40, 42.25, 600),
})


# ============================================================== 用法 A：一键
def demo_one_shot(outdir: pathlib.Path) -> None:
    dm = maps.DistrictMap(DISTRICTS)
    fig, ax, gs = dm.figure(cols=[0.35, 3.0], n_sub=2)

    dm.draw(ax, VALUES, TEXTS, hot=HOT, norm="log",
            dots=[(dm.clip(SITES), theme.MUTED)],
            km=20)

    # 右侧随手画一条柱状图
    ax_r = fig.add_subplot(gs[1, 1])
    names = sorted(VALUES, key=VALUES.get)
    ax_r.barh(names, [VALUES[n] for n in names], color=theme.MUTED)
    ax_r.set_axis_off()
    ax_r.text(0, 1.02, "事件数（log 色阶同图）", transform=ax_r.transAxes,
              fontsize=9, color=theme.INK, va="bottom")

    fig.savefig(outdir / "district_one_shot.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("saved district_one_shot.png")


# ============================================================== 用法 B：手动组合
def demo_composable(outdir: pathlib.Path) -> None:
    dm = maps.DistrictMap(DISTRICTS)
    fig, ax, gs = dm.figure(cols=[0.35, 3.0], n_sub=2)

    # 1) 自己算色阶，填色
    cmap, norm = maps.colorize(VALUES, norm="log")
    dm.fill(ax, {n: cmap(norm(v)) for n, v in VALUES.items()})

    # 2) 叠站点
    dm.dots(ax, dm.clip(SITES), color=theme.INK, s=1.2)

    # 3) 描外缘
    dm.outline(ax)

    # 4) ← 在这里插自己的图层：hot 区县中心画个星
    for name in HOT:
        lng, lat = dm.anchors[name]
        ax.plot(lng, lat, "*", ms=14, color=theme.MAIN,
                mec="white", mew=0.7, zorder=7)

    # 5) 标注 + 装饰
    dm.labels(ax, TEXTS, hot=HOT)
    dm.decorate(ax, km=20)

    # 6) 右侧放色阶条
    ax_r = fig.add_subplot(gs[1, 1])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    fig.colorbar(sm, cax=ax_r, orientation="vertical")
    ax_r.set_ylabel("事件数（log）", fontsize=9, color=theme.INK)

    fig.savefig(outdir / "district_composable.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("saved district_composable.png")


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parent / "out"
    out.mkdir(exist_ok=True)
    demo_one_shot(out)
    demo_composable(out)


