#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对外展示看板：沈阳移动信令 · 国庆傍晚西塔访客洞察。

只用聚合结果（AGENTS.md 1.4 / 1.5）：本文件不输出任何 IMSI，所有图表与指标
都来自 data/signal.db 的 ads_* / dws_* 汇总表；明细表只做 count / median / avg。

启动（工作目录 = dashboard/；streamlit / altair 装在 base 环境）：
    E:\\Anaconda3\\python.exe -m streamlit run visitor_dashboard.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signal_insight import config  # noqa: E402

# ── 色板：与 viz/theme.py 语义色一致，看板与报告同色 ────────────────────
MAIN, MAIN_DARK, MAIN_LIGHT, MAIN_MID = "#1D6FA5", "#174E73", "#DDEAF4", "#7FB3D9"
GRAY, GRAY_DARK = "#C4CAD3", "#8E99A6"
INK, MUTED, FAINT = "#15222D", "#65717B", "#9AA3AB"
RED, AMBER, GREEN = "#B3423A", "#B7791F", "#2D6A56"
ORANGE = "#C97F2E"
PAPER, LINE = "#F3F4F1", "#D4D8D2"
HERO_BG, HERO_INK, HERO_MUT, HERO_ACC = "#0D1A28", "#EEF2F5", "#9CAEBC", "#F0A640"
SEG_COLOR = {"市内来访": MAIN, "周边居民": MAIN_MID, "外地来客": ORANGE, "过夜地不明": GRAY}
AREA_COLOR = {"西塔": MAIN, "太原街商圈": ORANGE, "中街商圈": GREEN}
CALIBER_ORDER = ["任意一条信令", "停留≥30分钟", "停留≥60分钟", "停留≥120分钟"]

PAGES = ["概览", "到访口径", "空间口径", "时间节奏", "停留识别", "客群构成", "商圈联动", "工程与边界"]


# ── 数据访问：只读连接，结果缓存 ────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=900)
def q(sql: str) -> pd.DataFrame:
    con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    try:
        return pd.read_sql(sql, con)
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=900)
def one(sql: str):
    df = q(sql)
    return df.iloc[0, 0]


def n(x) -> str:
    return f"{int(round(float(x))):,}"


def pc(x, digits: int = 2) -> str:
    return f"{float(x) * 100:.{digits}f}%"


def hours(minutes: float) -> str:
    return f"{minutes / 60:.1f}"


# ── 样式 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="西塔访客洞察 · 沈阳移动信令",
    page_icon="◧",
    layout="wide",
    initial_sidebar_state="expanded",
)

FONT = "'Noto Sans CJK SC', 'Noto Sans SC', 'Source Han Sans SC', 'Microsoft YaHei', sans-serif"

st.markdown(
    f"""
<style>
  :root {{
    --ink: {INK}; --ink2: #33414D; --muted: {MUTED}; --faint: {FAINT};
    --line: {LINE}; --line2: #E6E8E1; --paper: {PAPER}; --paper2: #E9EBE5; --card: #FFFFFF;
    --accent: {MAIN}; --accent-dk: {MAIN_DARK}; --accent-lt: #E3EEF6;
    --hero: {HERO_BG}; --hero-ink: {HERO_INK}; --hero-mut: {HERO_MUT};
    --hero-line: rgba(150,178,200,.28); --hero-acc: {HERO_ACC};
    --shadow: 0 1px 2px rgba(21,34,45,.04), 0 10px 26px rgba(21,34,45,.055);
    --serif: "Noto Serif CJK SC", "Noto Serif SC", "Source Han Serif SC", SimSun, serif;
    --num: "Bahnschrift SemiCondensed", "Cascadia Mono", Consolas, "Noto Sans Mono", monospace;
  }}

  #MainMenu, footer {{visibility: hidden;}}
  header[data-testid="stHeader"], div[data-testid="stToolbar"], div[data-testid="stDecoration"] {{
    display: none !important;
  }}
  .stApp {{background: var(--paper);}}
  .block-container {{padding: 24px 10px 44px; max-width: 1180px;}}
  html, body, [class*="css"] {{
    font-family: {FONT};
    color: var(--ink);
    -webkit-font-smoothing: antialiased;
  }}

  /* ── 顶部条 ─────────────────────────────────────────────────────── */
  .mast {{background: var(--card); border: 1px solid var(--line); border-radius: 16px;
          padding: 15px 22px; display: flex; justify-content: space-between;
          align-items: center; gap: 32px; box-shadow: var(--shadow);}}
  .mast .kicker {{font-size: 10px; letter-spacing: .22em; color: var(--accent);
                  font-weight: 600; text-transform: uppercase;}}
  .mast h1 {{font-family: var(--serif); font-size: 17px; line-height: 1.4; font-weight: 700;
             margin: 4px 0 0; color: var(--ink); letter-spacing: .01em;}}
  .mast dl {{margin: 0; display: flex; gap: 26px; text-align: right;}}
  .mast dt {{font-size: 9.5px; letter-spacing: .12em; color: var(--faint); margin: 0;}}
  .mast dd {{margin: 2px 0 0; font-size: 12px; font-weight: 600; color: var(--ink2);
             font-variant-numeric: tabular-nums;}}

  /* ── 首屏（暗色）───────────────────────────────────────────────── */
  .st-key-hero {{background: var(--hero); border-radius: 18px; padding: 30px 34px 16px;
                 box-shadow: 0 18px 40px rgba(13,26,40,.18);}}
  .st-key-hero [data-testid="stVerticalBlock"] {{gap: .55rem;}}
  .st-key-hero [data-testid="stImage"] img {{border: none; border-radius: 8px;}}
  .hero-k {{font-size: 11.5px; letter-spacing: .1em; color: var(--hero-mut); margin: 0;}}
  .hero-h1 {{font-family: var(--serif); font-size: clamp(32px, 3.2vw, 50px); line-height: 1.14;
             font-weight: 800; color: var(--hero-ink); letter-spacing: .02em; margin: 12px 0 14px;}}
  .hero-lead {{font-size: 14px; line-height: 1.95; color: rgba(238,242,245,.88); margin: 0 0 4px;}}
  .hero-rule {{height: 1px; background: var(--hero-line); margin: 20px 0 14px;}}
  .hero-clock {{display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;}}
  .hero-clock .hh {{font-family: var(--num); font-size: 50px; font-weight: 600; line-height: .95;
                    color: var(--hero-ink);}}
  .hero-clock .hh small {{font-size: 21px; color: var(--hero-mut); font-weight: 500;}}
  .hero-clock .obs {{font-size: 12.5px; color: var(--hero-mut);}}
  .hero-clock .obs b {{color: var(--hero-ink); font-weight: 600; font-family: var(--num);}}
  .hero-cap {{font-size: 12.5px; line-height: 1.85; color: rgba(238,242,245,.92); margin: 9px 0 11px;}}
  .hero-list {{list-style: none; padding: 0; margin: 0; display: grid; gap: 7px;}}
  .hero-list li {{display: grid; grid-template-columns: 6.4em minmax(0,1fr) 3.4em 2.6em;
                  align-items: center; gap: 10px; font-size: 12px; color: var(--hero-ink);}}
  .hero-list .k {{color: var(--hero-mut);}}
  .hero-list .bar {{height: 5px; background: var(--hero-line); border-radius: 3px; overflow: hidden;}}
  .hero-list .bar i {{display: block; height: 100%; background: var(--hero-acc);}}
  .hero-list li.dim .bar i {{background: #5C7385;}}
  .hero-list .v, .hero-list .p {{font-family: var(--num); text-align: right;}}
  .hero-list .p {{color: var(--hero-mut);}}
  .hero-spark {{margin-top: 16px;}}
  .hero-spark svg {{display: block; width: 100%; height: 46px;}}
  .hero-spark p {{font-size: 10.5px; color: var(--hero-mut); margin: 5px 0 0;}}
  .hero-note {{font-size: 11px; color: var(--hero-mut); line-height: 1.8; margin: 8px 0 0;}}
  .st-key-hero [data-testid="stSlider"] {{padding: 2px 0 6px;}}
  .st-key-hero [data-testid="stSlider"] label p {{color: var(--hero-mut) !important;
      font-size: 11px !important; letter-spacing: .14em;}}
  .st-key-hero [data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {{
      background: var(--hero-acc) !important; border-color: var(--hero-acc) !important;}}
  .st-key-hero [data-testid="stSliderTickBarMin"], .st-key-hero [data-testid="stSliderTickBarMax"] {{
      color: var(--hero-mut) !important;}}

  /* ── 页标题 ─────────────────────────────────────────────────────── */
  .ph {{margin: 34px 0 16px; padding-bottom: 13px; border-bottom: 1px solid var(--line);}}
  .ph .k {{font-size: 10px; letter-spacing: .18em; color: var(--accent); font-weight: 600;}}
  .ph h2 {{font-family: var(--serif); font-size: 27px; font-weight: 700; letter-spacing: .01em;
           margin: 8px 0 7px; color: var(--ink);}}
  .ph p {{margin: 0; font-size: 12.5px; color: var(--muted); line-height: 1.8;}}

  /* ── 指标卡 ─────────────────────────────────────────────────────── */
  .kpi {{position: relative; background: var(--card); border: 1px solid var(--line);
         border-radius: 14px; padding: 17px 18px 15px; height: 100%; box-shadow: var(--shadow);}}
  .kpi .kpi-l {{font-size: 11px; letter-spacing: .06em; color: var(--muted);}}
  .kpi .kpi-v {{font-family: var(--num); font-size: 31px; font-weight: 600; letter-spacing: -.2px;
                color: var(--ink); margin-top: 8px; line-height: 1.15;}}
  .kpi .kpi-v .u {{font-family: {FONT}; font-size: 12px; font-weight: 500; color: var(--muted);
                   letter-spacing: 0; margin-left: 5px;}}
  .kpi .kpi-n {{font-size: 10.5px; color: var(--faint); margin-top: 9px; line-height: 1.6;}}

  /* ── 结论框、注释、小节头 ───────────────────────────────────────── */
  .lead {{background: var(--card); border: 1px solid var(--line); border-radius: 14px;
          padding: 17px 22px; font-size: 13.5px; line-height: 2.0; color: var(--ink2);
          box-shadow: var(--shadow);}}
  .lead b {{color: var(--ink); font-weight: 700;}}

  .sec-h {{display: flex; align-items: baseline; gap: 10px; margin: 30px 0 0;
           padding-bottom: 8px; border-bottom: 1px solid var(--line);}}
  .sec-h .i {{font-family: var(--num); font-size: 11px; font-weight: 600; letter-spacing: .1em;
              color: var(--accent);}}
  .sec-h h3 {{margin: 0; font-family: var(--serif); font-size: 16.5px; font-weight: 700;
              letter-spacing: .01em; color: var(--ink);}}
  .sec-n {{font-size: 11px; color: var(--faint); line-height: 1.75; margin: 8px 0 12px;}}

  .note {{font-size: 11px; color: var(--muted); line-height: 1.85; margin: 10px 0 0;
          padding-left: 11px; border-left: 2px solid var(--line);}}
  .foot {{border-top: 1px solid var(--line); margin-top: 38px; padding-top: 14px;
          font-size: 10.5px; color: var(--faint); line-height: 1.9;}}
  .pill {{display: inline-block; padding: 2px 9px; border: 1px solid var(--line); border-radius: 20px;
          font-size: 10px; letter-spacing: .06em; color: var(--muted); background: #FAFBF8;
          margin-right: 8px;}}

  /* ── 图表、图片、表格 ───────────────────────────────────────────── */
  div[data-testid="stVegaLiteChart"] {{background: var(--card); border: 1px solid var(--line);
                                       border-radius: 14px; padding: 12px 8px 6px;
                                       box-shadow: var(--shadow);}}
  div[data-testid="stImage"] img {{border-radius: 10px;}}

  table.tb {{width: 100%; border-collapse: separate; border-spacing: 0; background: var(--card);
             border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
             font-size: 12px; box-shadow: var(--shadow);}}
  table.tb th {{font-size: 10px; letter-spacing: .1em; color: var(--muted); font-weight: 600;
                text-align: left; padding: 11px 14px; background: #F7F8F4;
                border-bottom: 1px solid var(--line);}}
  table.tb td {{padding: 9px 14px; border-bottom: 1px solid #EFEFE9; color: var(--ink2);}}
  table.tb tr:last-child td {{border-bottom: none;}}
  table.tb tr:hover td {{background: #FAFBF8;}}
  table.tb td.num {{text-align: right; font-family: var(--num); font-size: 12.5px; color: var(--ink);}}
  table.tb tr.total td {{border-top: 1px solid var(--line); font-weight: 700; color: var(--ink);
                         background: #F7F8F4;}}

  /* ── 侧栏：圆角拟态 ─────────────────────────────────────────────── */
  section[data-testid="stSidebar"] {{background: #E9EBE5; border-right: 1px solid var(--line);}}
  section[data-testid="stSidebar"] .block-container {{padding: 18px 14px 28px;}}
  section[data-testid="stSidebar"] .sb {{font-size: 9.5px; letter-spacing: .2em; color: var(--faint);}}
  section[data-testid="stSidebar"] .sbt {{font-family: var(--serif); font-size: 17px; font-weight: 700;
                                         color: var(--ink); margin: 6px 0 3px; letter-spacing: .02em;}}
  section[data-testid="stSidebar"] .sbs {{font-size: 10.5px; color: var(--muted); line-height: 1.7;}}
  section[data-testid="stSidebar"] hr {{margin: 14px 0; border-color: rgba(21,34,45,.08);}}

  .sb-card {{background: #F1F2ED; border-radius: 16px; padding: 14px 15px 12px;
             box-shadow: inset 0 1px 0 rgba(255,255,255,.9), 0 8px 20px rgba(21,34,45,.06);
             border: 1px solid rgba(255,255,255,.55); margin-bottom: 12px;}}
  .sb-card .sb-t {{font-size: 9.5px; letter-spacing: .18em; color: var(--faint); margin-bottom: 8px;}}
  .sb-row {{display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: 11px;
            color: var(--muted);}}
  .sb-row b {{color: var(--ink); font-weight: 600; font-size: 10.5px; font-family: var(--num);}}
  .sb-note {{font-size: 10px; color: var(--faint); line-height: 1.75;}}

  div[role="radiogroup"] {{gap: 4px;}}
  div[role="radiogroup"] label {{padding: 9px 12px; margin: 0; border-radius: 12px; cursor: pointer;
                                 transition: background .14s ease, box-shadow .14s ease;
                                 border: 1px solid transparent;}}
  div[role="radiogroup"] label > div:has(input) {{display: none;}}
  div[role="radiogroup"] label:hover {{background: rgba(255,255,255,.55);}}
  div[role="radiogroup"] label:has(input:checked) {{background: #FFFFFF;
      box-shadow: inset 0 1px 0 #fff, 0 6px 14px rgba(21,34,45,.08); border-color: rgba(21,34,45,.06);}}
  div[role="radiogroup"] label:has(input:checked) p {{color: var(--accent-dk) !important;
                                                      font-weight: 700 !important;}}
  div[role="radiogroup"] label p {{font-size: 12.5px !important; color: var(--ink2) !important;}}

  div[data-baseweb="select"] > div {{border-radius: 12px; border-color: rgba(21,34,45,.10);
                                     font-size: 12px; background: #F1F2ED;
                                     box-shadow: inset 0 1px 2px rgba(21,34,45,.05);}}
  section[data-testid="stSidebar"] .stCaption {{color: var(--faint);}}
  section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    font-size: 10px !important; letter-spacing: .14em; color: var(--faint) !important;
    text-transform: uppercase; margin: 2px 0 4px;}}
</style>
""",
    unsafe_allow_html=True,
)

_SEC = [0]


def sec(title: str, note: str = "") -> None:
    _SEC[0] += 1
    st.markdown(
        f'<div class="sec-h"><span class="i">{_SEC[0]:02d}</span><h3>{title}</h3></div>',
        unsafe_allow_html=True,
    )
    if note:
        st.markdown(f'<div class="sec-n">{note}</div>', unsafe_allow_html=True)


def page_head(index: int, title: str, question: str) -> None:
    _SEC[0] = 0
    st.markdown(
        f'<div class="ph"><div class="k">SECTION {index:02d}</div>'
        f"<h2>{title}</h2><p>{question}</p></div>",
        unsafe_allow_html=True,
    )


def lead(html: str) -> None:
    st.markdown(f'<div class="lead">{html}</div>', unsafe_allow_html=True)


def kpi(col, label: str, value: str, note: str = "", unit: str = "") -> None:
    u = f'<span class="u">{unit}</span>' if unit else ""
    col.markdown(
        f'<div class="kpi"><div class="kpi-l">{label}</div>'
        f'<div class="kpi-v">{value}{u}</div>'
        f'<div class="kpi-n">{note}</div></div>',
        unsafe_allow_html=True,
    )


def html_table(headers, rows, total=None, aligns=None) -> None:
    aligns = aligns or ["l"] + ["r"] * (len(headers) - 1)
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(
            f'<td class="{"num" if aligns[i] == "r" else ""}">{c}</td>' for i, c in enumerate(row)
        )
        body.append(f"<tr>{cells}</tr>")
    if total:
        cells = "".join(
            f'<td class="{"num" if aligns[i] == "r" else ""}">{c}</td>' for i, c in enumerate(total)
        )
        body.append(f'<tr class="total">{cells}</tr>')
    st.markdown(f'<table class="tb"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>',
                unsafe_allow_html=True)


def two_col(left, right) -> None:
    """并排两张“可以说 / 不能说”卡片。"""
    def card(title, color, items):
        lis = "".join(
            f'<li style="padding:8px 0;border-bottom:1px solid var(--line2);font-size:12.5px;'
            f'line-height:1.8;color:var(--ink2)">{i}</li>'
            for i in items
        )
        return (
            f'<div style="background:var(--card);border:1px solid var(--line);'
            f'border-top:2px solid {color};padding:15px 20px 6px">'
            f'<div style="font-size:10.5px;letter-spacing:.14em;color:{color};font-weight:600;'
            f'margin-bottom:4px">{title}</div>'
            f'<ul style="list-style:none;margin:0;padding:0">{lis}</ul></div>'
        )

    st.markdown(
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
        + card(*left) + card(*right) + "</div>",
        unsafe_allow_html=True,
    )


def styled(ch, height: int = 320):
    return (
        ch.properties(height=height)
        .configure_view(stroke=None)
        .configure(background="transparent")
        .configure_axis(
            grid=True,
            gridColor="#EAEBE4",
            gridWidth=1,
            domainColor="#D4D8D2",
            tickColor="#D4D8D2",
            labelColor="#65717B",
            titleColor="#9AA3AB",
            labelFont=FONT,
            titleFont=FONT,
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight=500,
            titlePadding=10,
            labelPadding=4,
        )
        .configure_legend(
            labelColor="#65717B", titleColor="#9AA3AB", labelFont=FONT,
            labelFontSize=11, orient="top", direction="horizontal",
            title=None, symbolSize=80, symbolType="square",
        )
        .configure_title(font=FONT, fontSize=12, color="#65717B", anchor="start", fontWeight=500)
    )


# ── 取数 ────────────────────────────────────────────────────────────────
N_ODS = one("SELECT COUNT(*) FROM ods_signal")
N_DWD = one("SELECT COUNT(*) FROM dwd_signal")
N_USERS = one("SELECT COUNT(DISTINCT imsi) FROM dwd_signal")
N_STAY = one("SELECT COUNT(*) FROM dws_stay")
N_STAY_USER = one("SELECT COUNT(DISTINCT imsi) FROM dws_stay")
N_VISITOR = one("SELECT COUNT(*) FROM dws_visitor")
N_XITA = one(
    """SELECT 人数 FROM ads_caliber_visitors
       WHERE 半径 = '500米' AND 口径 = '停留>=30分钟'"""
)
VISITOR = q("SELECT arrive_hour, xita_stay_min, after_23 FROM dws_visitor")
MED_STAY = float(VISITOR["xita_stay_min"].median())
SHARE_AFTER23 = float(VISITOR["after_23"].mean())
HOTSPOT = q("SELECT * FROM dim_hotspot").iloc[0]
LAST_BATCH = one("SELECT MAX(批次) FROM etl_log")
ETL = q(f"SELECT * FROM etl_log WHERE 批次 = '{LAST_BATCH}' ORDER BY rowid")
LINK = q("SELECT * FROM ads_xita_linkage")
LINK_UP = LINK[LINK["地点"] == "太原街商圈"].iloc[0]
TAIYUAN_SHARE = float(LINK_UP["之前占比"])
TAIYUAN_UP_N = int(LINK_UP["之前人数"])
TAIYUAN_AFTER = int(LINK_UP["之后人数"])
_ZJ = LINK[LINK["地点"] == "中街商圈"].iloc[0]
ZHONGJIE_UP_N = int(_ZJ["之前人数"])
ZHONGJIE_SHARE = float(_ZJ["之前占比"])
ZHONGJIE_AFTER = int(_ZJ["之后人数"])
GAP_TAIYUAN, GAP_ZHONGJIE = 70, 134

# ── 侧栏 ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:4px 6px 14px">'
        '<div class="sb">SIGNAL INSIGHT</div>'
        '<div class="sbt">西塔访客洞察</div>'
        '<div class="sbs">沈阳移动信令 · 2018 国庆样本 · 对外展示</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    page = st.radio("导航", PAGES, label_visibility="collapsed")

    st.markdown('<div class="sb" style="margin:18px 0 2px 4px">展示口径</div>', unsafe_allow_html=True)
    radius = st.selectbox("热点半径", ["300 米", "500 米", "1000 米"], index=1)
    caliber = st.selectbox("到访口径", CALIBER_ORDER, index=1)

    _status = [
        ("业务日期", config.ANALYSIS_DAY),
        ("样本用户", f"{n(N_USERS)} 人"),
        ("明细记录", f"{n(N_DWD)} 条"),
        ("运行批次", LAST_BATCH),
    ]
    st.markdown(
        '<div class="sb-card"><div class="sb-t">数据状态</div>'
        + "".join(
            f'<div class="sb-row"><span>{k}</span><b>{v}</b></div>' for k, v in _status
        )
        + "</div>"
        '<div class="sb-note" style="padding:0 6px">样本为历史脱敏数据；页面上的一切人数均为'
        "中国移动用户样本内口径，换口径人数会变，差 2.9 倍不是误差而是定义不同。</div>",
        unsafe_allow_html=True,
    )

RADIUS_LABEL = radius.replace(" ", "")  # 300米
CAL_DF = q("SELECT * FROM ads_caliber_visitors")


def caliber_count(radius_label: str, caliber_label: str) -> int:
    row = CAL_DF[(CAL_DF["半径"] == radius_label) & (CAL_DF["口径"] == caliber_label)]
    return int(row["人数"].iloc[0]) if len(row) else 0


CUR = caliber_count(RADIUS_LABEL, caliber)

# ── 顶部条：首屏用暗色首图，其余页用细条 ────────────────────────────────
def topbar() -> None:
    st.markdown(
        f"""
<header class="mast">
  <div>
    <div class="kicker">Signal Insight · 沈阳移动信令</div>
    <h1>国庆傍晚，来西塔的是谁</h1>
  </div>
  <dl>
    <div><dt>样本日期</dt><dd>{config.ANALYSIS_DAY}</dd></div>
    <div><dt>当前口径</dt><dd>{radius} · {caliber}</dd></div>
    <div><dt>样本用户</dt><dd>{n(N_USERS)} 人</dd></div>
  </dl>
</header>
""",
        unsafe_allow_html=True,
    )
    st.write("")


# ── 1 概览（昼夜变色的六边形首屏，自动播放）──────────────────────────────
_HERO_JSON = ROOT / "dashboard" / "static" / "hero.json"

_HERO_TPL = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<style>
  html,body{margin:0;padding:0;background:transparent;}
  *{box-sizing:border-box;}
  .hero{--h-bg:#0D1A28;--h-ink:#EEF2F5;--h-muted:#9CAEBC;--h-line:rgba(150,178,200,.3);--h-acc:#F0A640;
    height:100%;background:var(--h-bg);color:var(--h-ink);border-radius:18px;
    padding:30px 34px 22px;display:flex;flex-direction:column;gap:10px;
    font-family:"Noto Sans CJK SC","Noto Sans SC","Microsoft YaHei",sans-serif;
    transition:background .5s linear,color .35s linear;}
  .grid{display:grid;grid-template-columns:minmax(280px,400px) minmax(0,1fr);
    grid-template-areas:"copy map" "read map";grid-template-rows:auto 1fr;
    column-gap:36px;}
  .copy{grid-area:copy;}
  .k{margin:0 0 14px;font-size:11.5px;letter-spacing:.1em;color:var(--h-muted);}
  h1{margin:0 0 16px;font-family:"Noto Serif CJK SC","Noto Serif SC","Source Han Serif SC",SimSun,serif;
    font-size:52px;line-height:1.1;font-weight:800;letter-spacing:.03em;color:var(--h-ink);
    transition:color .35s linear;}
  .lead{margin:0;font-size:13.5px;line-height:1.95;color:var(--h-ink);opacity:.9;max-width:25em;}
  .readout{grid-area:read;border-top:1px solid var(--h-line);padding-top:13px;align-self:start;}
  .clock{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;}
  .hh{font-family:"Bahnschrift SemiCondensed",Consolas,monospace;font-variant-numeric:tabular-nums;
    font-size:46px;line-height:1;font-weight:600;color:var(--h-ink);}
  .hh small{font-size:21px;color:var(--h-muted);font-weight:500;}
  .obs{font-size:12.5px;color:var(--h-muted);}
  .obs b{color:var(--h-ink);font-weight:600;font-family:"Bahnschrift SemiCondensed",Consolas,monospace;}
  .rd-cap{min-height:4.2em;margin:8px 0 11px;font-size:12.5px;line-height:1.85;color:var(--h-ink);opacity:.94;}
  .rd-list{list-style:none;margin:0;padding:0;display:grid;gap:7px;}
  .rd-list li{display:grid;grid-template-columns:6.6em minmax(0,1fr) 3.6em 2.6em;align-items:center;
    gap:10px;font-size:12px;}
  .rd-list .k2{color:var(--h-muted);}
  .bar{height:5px;background:var(--h-line);border-radius:3px;overflow:hidden;}
  .bar i{display:block;height:100%;width:0;background:var(--h-acc);transition:width .5s cubic-bezier(.4,0,.2,1);}
  .rd-list li.dim .bar i{background:var(--h-muted);}
  .v,.p{font-family:"Bahnschrift SemiCondensed",Consolas,monospace;text-align:right;
    font-variant-numeric:tabular-nums;}
  .p{color:var(--h-muted);}
  .spark{margin-top:12px;position:relative;}
  .spark svg{display:block;width:100%;height:52px;overflow:visible;}
  .spark .dot{position:absolute;width:7px;height:7px;margin:-3.5px 0 0 -3.5px;border-radius:50%;
    background:var(--h-acc);box-shadow:0 0 0 3px color-mix(in srgb,var(--h-acc) 22%,transparent);}
  .spark p{margin:3px 0 0;font-size:10.5px;color:var(--h-muted);}
  .map-wrap{grid-area:map;min-width:0;display:flex;flex-direction:column;}
  .map-box{position:relative;height:558px;max-width:100%;aspect-ratio:26.5/23.5;margin-left:auto;border-radius:12px;overflow:hidden;}
  .map-box canvas{position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:pan-y;}
  .map-tip{position:absolute;pointer-events:none;background:#fff;color:#15222D;font-size:11.5px;line-height:1.4;
    padding:4px 8px;border-radius:4px;white-space:nowrap;transform:translate(-50%,calc(-100% - 10px));
    box-shadow:0 2px 10px rgba(0,0,0,.25);}
  .map-ctl{display:flex;align-items:center;gap:12px;margin:10px 0 0;}
  .play{appearance:none;display:inline-flex;align-items:center;gap:7px;border:1px solid var(--h-line);
    background:transparent;color:var(--h-ink);font:600 12.5px inherit;padding:6px 13px 6px 10px;
    border-radius:999px;cursor:pointer;flex:none;}
  .play:hover{border-color:var(--h-muted);}
  .play svg{width:11px;height:11px;fill:currentColor;}
  .play .i-pause{display:none;}
  .play[aria-pressed="true"] .i-pause{display:block;}
  .play[aria-pressed="true"] .i-play{display:none;}
  .spd{display:flex;gap:4px;flex:none;}
  .spd button{appearance:none;border:1px solid var(--h-line);background:transparent;color:var(--h-muted);
    font:600 12px inherit;padding:5px 10px;border-radius:999px;cursor:pointer;}
  .spd button[aria-pressed="true"]{background:var(--h-acc);border-color:var(--h-acc);color:var(--h-bg);}
  .slider{flex:1;min-width:120px;}
  .slider input{width:100%;margin:0;accent-color:var(--h-acc);cursor:pointer;}
  .ticks{position:relative;height:16px;margin:0 6px;font:10.5px "Bahnschrift SemiCondensed",Consolas,monospace;
    color:var(--h-muted);}
  .ticks span{position:absolute;transform:translateX(-50%);}
  .note{margin:6px 0 0;font-size:10.5px;line-height:1.75;color:var(--h-muted);}
</style></head><body>
<header class="hero">
 <div class="grid">
  <div class="copy">
   <p class="k">沈阳手机信令数据分析 · 2018 国庆样本</p>
   <h1><span style="white-space:nowrap">__NUSERS__ 个人的</span><br>国庆一天</h1>
   <p class="lead">2018 年 10 月 3 日，国庆假期第三天。运营商给了我们沈阳 __NUSERS__ 名手机用户
     这一天的信令：__NODS__ 条记录，每一条都是手机和基站打的一次招呼。看这群人一天里都在哪。</p>
  </div>
  <div class="readout">
   <div class="clock"><span class="hh"><span id="rd-h">19</span><small>:<span id="rd-m">00</span></small></span>
     <span class="obs">可定位 <b id="rd-obs">—</b> 人</span></div>
   <p class="rd-cap" id="rd-cap"></p>
   <ul class="rd-list">
    <li data-k="xita"><span class="k2">西塔 500 米内</span><span class="bar"><i></i></span><span class="v"></span><span class="p"></span></li>
    <li data-k="ty" class="dim"><span class="k2">太原街商圈</span><span class="bar"><i></i></span><span class="v"></span><span class="p"></span></li>
    <li data-k="zj" class="dim"><span class="k2">中街商圈</span><span class="bar"><i></i></span><span class="v"></span><span class="p"></span></li>
    <li data-k="out" class="dim"><span class="k2">和平区以外</span><span class="bar"><i></i></span><span class="v"></span><span class="p"></span></li>
   </ul>
   <div class="spark"><svg id="spark" viewBox="0 0 240 54" preserveAspectRatio="none"></svg>
     <p>西塔人数占可定位人数的比例，0 点到 23 点</p></div>
  </div>
  <div class="map-wrap">
   <div class="map-box"><canvas id="map" role="img"
     aria-label="沈阳中心城区六边形人数地图，随小时变化：白天人群散在全城，19 点大量聚集在西塔。"></canvas>
     <div class="map-tip" id="map-tip" hidden></div></div>
   <div class="map-ctl">
    <button class="play" id="play" type="button" aria-pressed="false">
      <svg class="i-play" viewBox="0 0 12 12"><path d="M2 1l9 5-9 5z"/></svg>
      <svg class="i-pause" viewBox="0 0 12 12"><path d="M2 1h3v10H2zM7 1h3v10H7z"/></svg><span>播放</span></button>
    <div class="spd" role="group" aria-label="播放速度">
      <button type="button" data-spd="0.5" aria-pressed="false">慢</button>
      <button type="button" data-spd="1" aria-pressed="true">常速</button>
      <button type="button" data-spd="2" aria-pressed="false">快</button></div>
    <div class="slider"><input id="hour" type="range" min="0" max="23" step="1" value="19" aria-label="选择小时">
      <div class="ticks"><span style="left:0%">0 点</span><span style="left:26.09%">6</span>
        <span style="left:52.17%">12</span><span style="left:78.26%">18</span><span style="left:100%">23</span></div></div>
   </div>
   <p class="note">以西塔为原点，视窗约 27 × 24 公里。每人每小时一个位置：覆盖该小时 30 分钟以上的停留点，
     没有就取该小时信令的中位位置。六边形边长 0.55 公里，颜色越浓人越多；少于 5 人的格子不显示。
     虚线圈是西塔 500 米。白天底色调浅，夜里转深。</p>
  </div>
 </div>
</header>
<script id="hero-data" type="application/json">__DATA__</script>
<script id="caps" type="application/json">__CAPS__</script>
<script>
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- 工具 ---------- */
  function fmt(nv) { return String(Math.round(nv)).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function pct(v) { return v < 10 ? v.toFixed(1) : v.toFixed(0); }
  function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function rgba(c, a) { return "rgba(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + "," + (a == null ? 1 : a) + ")"; }
  function hexc(c) { return "#" + c.map(function (v) { var s = Math.round(v).toString(16); return s.length < 2 ? "0" + s : s; }).join(""); }
  function smooth(t) { return t * t * (3 - 2 * t); }
  // 昼夜系数：0 = 夜，1 = 昼
  function light(h) {
    h = ((h % 24) + 24) % 24;
    if (h < 5) return 0;
    if (h < 6) return smooth(h - 5);
    if (h <= 17) return 1;
    if (h < 18) return 1 - smooth(h - 17);
    return 0;
  }
  var NIGHT = { bg: [13, 26, 40], hex: [240, 166, 64], hot: [255, 232, 188], line: [150, 178, 200], ink: [238, 242, 245], label: [156, 174, 188] };
  var DAY = { bg: [231, 236, 238], hex: [29, 111, 165], hot: [9, 52, 84], line: [60, 80, 95], ink: [21, 34, 45], label: [86, 99, 110] };

  var D, CAPS;
  try {
    D = JSON.parse($("#hero-data").textContent);
    CAPS = JSON.parse($("#caps").textContent);
  } catch (err) { D = null; }

  var cur = 19, playing = false;
  if (!D) return;

  var E = D.ext, S = D.s, R3 = Math.sqrt(3), KMIN = D.k_min || 5, VMAX = D.vmax, HOT0 = 400, HOT1 = 2000;
  var HY = D.hourly, OBS = HY.obs;
  var cells = D.hex.map(function (a) {
    return { q: a[0], r: a[1], x: S * (R3 * a[0] + R3 / 2 * a[1]), y: S * 1.5 * a[1], c: a.slice(2) };
  });
  var byKey = {};
  cells.forEach(function (c) { byKey[c.q + "," + c.r] = c; });
  var CORNERS = [];
  for (var i = 0; i < 6; i++) { var ang = Math.PI / 180 * (60 * i - 30); CORNERS.push([Math.cos(ang), Math.sin(ang)]); }

  var heroEl = $(".hero"), box = $(".map-box"), cv = $("#map"), ctx = cv.getContext("2d"), tip = $("#map-tip");
  var slider = $("#hour"), btn = $("#play"), btnTxt = btn.querySelector("span");
  var rdH = $("#rd-h"), rdM = $("#rd-m"), rdObs = $("#rd-obs"), rdCap = $("#rd-cap");
  var rows = {};
  $$(".rd-list li").forEach(function (li) { rows[li.getAttribute("data-k")] = li; });
  var FONT = getComputedStyle(document.body).fontFamily;

  var W = 0, H = 0, K = 1, OX = 0, OY = 0, DPR = 1;
  function px(x) { return OX + (x - E[0]) * K; }
  function py(y) { return OY + (E[3] - y) * K; }

  function valAt(arr, h) {
    var h0 = Math.floor(h) % 24, h1 = (h0 + 1) % 24, f = h - Math.floor(h);
    return arr[h0] + (arr[h1] - arr[h0]) * f;
  }

  function label(text, x, y, size, color, halo, align, base, weight) {
    ctx.font = (weight || 500) + " " + size + "px " + FONT;
    ctx.textAlign = align; ctx.textBaseline = base;
    ctx.lineJoin = "round"; ctx.lineWidth = 4; ctx.strokeStyle = rgba(halo, 0.92);
    ctx.strokeText(text, x, y);
    ctx.fillStyle = color; ctx.fillText(text, x, y);
  }

  function ring(r) {
    ctx.beginPath();
    for (var i = 0; i < r.length; i += 2) {
      var X = px(r[i]), Y = py(r[i + 1]);
      if (i) ctx.lineTo(X, Y); else ctx.moveTo(X, Y);
    }
    ctx.closePath();
  }

  function draw() {
    if (!W) return;
    var h = cur, L = light(h), day = L >= 0.5;
    var bg = mix(NIGHT.bg, DAY.bg, L), base = mix(NIGHT.hex, DAY.hex, L), hot = mix(NIGHT.hot, DAY.hot, L);
    var ink = day ? DAY.ink : NIGHT.ink;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.fillStyle = rgba(bg); ctx.fillRect(0, 0, W, H);

    // 区县边界
    ctx.setLineDash([]); ctx.lineJoin = "round"; ctx.lineWidth = 1;
    ctx.strokeStyle = rgba(day ? DAY.line : NIGHT.line, day ? 0.34 : 0.3);
    D.rings.forEach(function (r) { ring(r); ctx.stroke(); });

    // 六边形：对数色阶；400 人以上的格子向高亮色过渡并加光晕，放在最后画
    var lv = Math.log(VMAX / KMIN), rad = S * K * 0.95, hotList = [];
    function hexPath(X, Y, R) {
      ctx.beginPath();
      for (var i = 0; i < 6; i++) {
        var p = CORNERS[i], xx = X + p[0] * R, yy = Y - p[1] * R;
        if (i) ctx.lineTo(xx, yy); else ctx.moveTo(xx, yy);
      }
      ctx.closePath();
    }
    cells.forEach(function (c) {
      var v = valAt(c.c, h);
      if (v < KMIN) return;
      if (v > HOT0) { hotList.push([c, v]); return; }
      var t = Math.min(1, Math.log(v / KMIN) / lv), a = 0.14 + 0.8 * Math.pow(t, 0.85);
      hexPath(px(c.x), py(c.y), rad); ctx.fillStyle = rgba(base, a); ctx.fill();
    });
    hotList.forEach(function (e) {
      var m = Math.min(1, Math.log(e[1] / HOT0) / Math.log(HOT1 / HOT0));
      ctx.shadowColor = rgba(hot, 0.85); ctx.shadowBlur = 26 * m * DPR;
      hexPath(px(e[0].x), py(e[0].y), rad); ctx.fillStyle = rgba(mix(base, hot, m), 0.96); ctx.fill();
    });
    ctx.shadowBlur = 0; ctx.shadowColor = "rgba(0,0,0,0)";

    // 区县名
    D.labels.forEach(function (l) {
      label(l[0], px(l[1]), py(l[2]), 12, rgba(day ? DAY.label : NIGHT.label), bg, "center", "middle", 500);
    });

    // 商圈轮廓
    D.aoi.forEach(function (a) {
      ctx.lineWidth = 1.3; ctx.strokeStyle = rgba(ink, 0.8);
      ring(a.ring); ctx.stroke();
      var r = a.ring, far = [0, 0], fd = -1;
      for (var i = 0; i < r.length; i += 2) {
        var dd = r[i] * r[i] + r[i + 1] * r[i + 1];
        if (dd > fd) { fd = dd; far = [r[i], r[i + 1]]; }
      }
      var n = Math.sqrt(fd) || 1, ux = far[0] / n, uy = far[1] / n;
      label(a.name, px(far[0] + ux * 0.25), py(far[1] + uy * 0.25), 12.5, rgba(ink), bg,
        ux > 0.35 ? "left" : ux < -0.35 ? "right" : "center",
        uy > 0.35 ? "bottom" : uy < -0.35 ? "top" : "middle", 600);
    });

    // 西塔 500 米
    var cx = px(0), cy = py(0);
    ctx.setLineDash([4, 3]); ctx.lineWidth = 1.5; ctx.strokeStyle = rgba(ink, 0.95);
    ctx.beginPath(); ctx.arc(cx, cy, 0.5 * K, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
    label("西塔", cx + 0.5 * K + 6, cy, 14, rgba(ink), bg, "left", "middle", 700);

    // 比例尺 5 公里
    var len = 5 * K, x1 = W - 16, x0 = x1 - len, sy = H - 16;
    ctx.lineWidth = 1.5; ctx.strokeStyle = rgba(ink, 0.85);
    ctx.beginPath(); ctx.moveTo(x0, sy - 5); ctx.lineTo(x0, sy); ctx.lineTo(x1, sy); ctx.lineTo(x1, sy - 5); ctx.stroke();
    label("5 公里", (x0 + x1) / 2, sy - 5, 11.5, rgba(ink, 0.9), bg, "center", "bottom", 500);
  }

  function resize() {
    var r = box.getBoundingClientRect();
    if (!r.width || !r.height) return;
    DPR = Math.min(window.devicePixelRatio || 1, 2.5);
    W = r.width; H = r.height;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    K = Math.min(W / (E[1] - E[0]), H / (E[3] - E[2]));
    OX = (W - (E[1] - E[0]) * K) / 2; OY = (H - (E[3] - E[2]) * K) / 2;
    draw();
  }

  /* ---------- 首屏配色随昼夜变化 ---------- */
  var lastBg = "", lastDay = null;
  function theme(h) {
    var L = light(h), day = L >= 0.5, bg = hexc(mix(NIGHT.bg, DAY.bg, L));
    if (bg !== lastBg) { heroEl.style.setProperty("--h-bg", bg); lastBg = bg; }
    if (day !== lastDay) {
      lastDay = day;
      heroEl.style.setProperty("--h-ink", day ? "#15222D" : "#EEF2F5");
      heroEl.style.setProperty("--h-muted", day ? "#56636E" : "#9CAEBC");
      heroEl.style.setProperty("--h-line", day ? "rgba(60,80,95,.24)" : "rgba(150,178,200,.3)");
      heroEl.style.setProperty("--h-acc", day ? "#1D6FA5" : "#F0A640");
    }
  }

  /* ---------- 小曲线：西塔占比 ---------- */
  var spark = $("#spark"), share = OBS.map(function (o, i) { return o ? HY.xita[i] / o : 0; });
  var smax = Math.max.apply(null, share) || 1;
  function sy(v) { return 50 - v / smax * 44; }
  var d = share.map(function (v, i) { return (i ? "L" : "M") + (i / 23 * 240).toFixed(1) + " " + sy(v).toFixed(1); }).join(" ");
  spark.innerHTML = '<path d="' + d + ' L240 54 L0 54 Z" style="fill:var(--h-acc);opacity:.16"></path>' +
    '<path d="' + d + '" style="fill:none;stroke:var(--h-acc);stroke-width:1.6" vector-effect="non-scaling-stroke"></path>';
  var dot = document.createElement("i");
  dot.className = "dot"; dot.setAttribute("aria-hidden", "true");
  spark.parentNode.appendChild(dot);

  /* ---------- 读数 ---------- */
  function segment(h) { return h <= 5 ? "night" : h <= 9 ? "morning" : h <= 16 ? "day" : h <= 18 ? "dusk" : "evening"; }
  var shown = -1;
  function readout(h) {
    if (h === shown) return;
    shown = h;
    var o = OBS[h], x = o ? HY.xita[h] / o * 100 : 0, out = o ? HY.out[h] / o * 100 : 0;
    rdH.textContent = h;
    rdObs.textContent = fmt(o);
    var active = (h >= 9 && h <= 16) ? "out" : "xita";
    Object.keys(rows).forEach(function (k) {
      var li = rows[k], v = HY[k][h], p = o ? v / o * 100 : 0;
      li.querySelector(".bar i").style.width = p.toFixed(1) + "%";
      li.querySelector(".v").textContent = fmt(v);
      li.querySelector(".p").textContent = pct(p) + "%";
      li.classList.toggle("dim", k !== active);
    });
    rdCap.textContent = (CAPS[segment(h)] || "").replace("{h}", h).replace("{x}", x.toFixed(0))
      .replace("{out}", out.toFixed(0)).replace("{obs}", fmt(o));
    if (+slider.value !== h) slider.value = h;
    slider.setAttribute("aria-valuetext", h + " 点，可定位 " + fmt(o) + " 人，西塔 500 米内占 " + x.toFixed(0) + "%");
    dot.style.left = (h / 23 * 100) + "%";
    dot.style.top = sy(share[h]) + "px";
  }

  function setHour(h) {
    cur = h;
    theme(h); draw(); readout(Math.round(h) % 24);
    // 读数区按整点刷新，时钟的分钟位每帧都走，让人看出时间是连续的
    var mm = Math.floor((h - Math.floor(h)) * 60);
    if (rdM) rdM.textContent = (mm < 10 ? "0" : "") + mm;
  }

  /* ---------- 播放 ---------- */
  var raf = 0, MS_BASE = 1150, SPEED = 1;
  try { SPEED = parseFloat(localStorage.getItem("hero-speed")) || 1; } catch (e) { SPEED = 1; }
  var spdBox = $(".spd");
  if (spdBox) {
    $$("button", spdBox).forEach(function (b) {
      b.setAttribute("aria-pressed", String(parseFloat(b.getAttribute("data-spd")) === SPEED));
      b.addEventListener("click", function () {
        SPEED = parseFloat(b.getAttribute("data-spd"));
        try { localStorage.setItem("hero-speed", String(SPEED)); } catch (e) {}
        $$("button", spdBox).forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        if (playing) { var h = cur; stop(); run(h, h + 24); }
      });
    });
  }
  function msPerHour() { return MS_BASE / SPEED; }
  function stop() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0; playing = false;
    btn.setAttribute("aria-pressed", "false"); btnTxt.textContent = "播放";
  }
  function run(from, to) {
    stop();
    playing = true;
    btn.setAttribute("aria-pressed", "true"); btnTxt.textContent = "暂停";
    var t0 = null;
    function step(ts) {
      if (t0 === null) t0 = ts;
      var h = from + (ts - t0) / msPerHour();
      if (h >= to) { setHour(to % 24); stop(); return; }
      setHour(h % 24);
      raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
  }
  btn.addEventListener("click", function () {
    if (playing) { stop(); setHour(Math.round(cur) % 24); return; }
    var h = Math.round(cur) % 24;
    run(h, h + 24);
  });
  slider.addEventListener("input", function () { stop(); setHour(+slider.value); });

  /* ---------- 悬停提示 ---------- */
  function pick(e) {
    var r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    var x = (mx - OX) / K + E[0], y = E[3] - (my - OY) / K;
    var qf = (R3 / 3 * x - y / 3) / S, rf = (2 / 3 * y) / S, sf = -qf - rf;
    var q = Math.round(qf), rr = Math.round(rf), ss = Math.round(sf);
    var dq = Math.abs(q - qf), dr = Math.abs(rr - rf), ds = Math.abs(ss - sf);
    if (dq > dr && dq > ds) q = -rr - ss; else if (dr > ds) rr = -q - ss;
    var c = byKey[q + "," + rr], h = Math.round(cur) % 24, v = c ? c.c[h] : 0;
    tip.textContent = v >= KMIN ? (h + " 点，这一格 " + fmt(v) + " 人") : (h + " 点，这一格不足 " + KMIN + " 人，不显示");
    tip.style.left = mx + "px"; tip.style.top = my + "px";
    tip.hidden = false;
  }
  cv.addEventListener("pointermove", pick);
  cv.addEventListener("pointerdown", pick);
  cv.addEventListener("pointerleave", function () { tip.hidden = true; });

  if (window.ResizeObserver) new ResizeObserver(resize).observe(box);
  else window.addEventListener("resize", resize);
  resize();

  if (reduce) { setHour(19); }
  else {
    setHour(4);
    setTimeout(function () { if (!playing && cur === 4) run(4, 19); }, 1400);
  }
})();
</script></body></html>"""

_CAPS = {
    "night": "凌晨 {h} 点：多数人在各自的过夜地，散在全城，{out}% 在和平区以外。",
    "morning": "早上 {h} 点：人陆续出门，能定位到的人增加到 {obs}；西塔只有 {x}%。",
    "day": "白天 {h} 点：{out}% 的人在和平区以外，西塔只有 {x}%。",
    "dusk": "傍晚 {h} 点：人从全城往西塔聚，比例升到 {x}%。",
    "evening": "{h} 点：{x}% 的人在西塔 500 米内。这不是沈阳的常态，样本就是按傍晚到访西塔圈出来的。",
}


def page_overview() -> None:
    _SEC[0] = 0
    if _HERO_JSON.exists():
        html = (
            _HERO_TPL.replace("__DATA__", _HERO_JSON.read_text(encoding="utf-8"))
            .replace("__CAPS__", json.dumps(_CAPS, ensure_ascii=False))
            .replace("__NUSERS__", n(N_USERS))
            .replace("__NODS__", n(N_ODS))
        )
        components.html(html, height=730, scrolling=False)
    else:
        st.warning("首屏地图数据缺失，先运行 `python dashboard/build_hexdata.py` 生成 hero.json。")

    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "样本用户", n(N_USERS), "全天出现过信令的完整标识", unit="人")
    kpi(c2, "傍晚访客", n(N_VISITOR), f"占样本 {pc(N_VISITOR / N_USERS)}，17:00 后仍在西塔", unit="人")
    kpi(c3, "识别停留", n(N_STAY), f"{n(N_STAY_USER)} 人至少有一段，人均 {N_STAY / N_USERS:.2f} 个", unit="个")
    kpi(c4, "西塔停留中位", f"≥ {hours(MED_STAY)}", f"{pc(SHARE_AFTER23, 0)} 到 23 点仍在，数据 23:59 截止", unit="小时")

    st.write("")
    lead(
        f"<b>一句话结论：</b>国庆傍晚的西塔是“陡坡型”客流——17 点在场人数比 16 点翻一倍以上，"
        f"20 点达到峰值，{pc(SHARE_AFTER23, 0)} 的访客到 23 点仍未离开；"
        f"来的人以本市为主，{pc(TAIYUAN_SHARE, 1)} 的访客先到太原街再来西塔，中位间隔 70 分钟。"
        f"<br><span style='color:{MUTED};font-size:12.5px'>所有人数均为中国移动用户样本内口径，"
        f"等于下限而不是全市实际值。</span>"
    )

    sec("一天的形状：17 点起陡增，20 点见顶", "口径：该小时有信令落在西塔 500 米内的用户数；虚线为首次出现人数。")
    xh = q("SELECT * FROM ads_xita_hourly ORDER BY 小时")
    area = (
        alt.Chart(xh)
        .mark_area(color=MAIN, opacity=0.13, line=False)
        .encode(
            x=alt.X("小时:Q", axis=alt.Axis(values=list(range(0, 24, 3)), title="时刻（时）"), scale=alt.Scale(domain=[0, 23])),
            y=alt.Y("在场人数:Q", title="人数"),
        )
    )
    line = (
        alt.Chart(xh)
        .mark_line(color=MAIN, strokeWidth=2.6, point=alt.OverlayMarkDef(size=45, filled=True))
        .encode(x="小时:Q", y="在场人数:Q", tooltip=["小时", "在场人数", "首次出现人数"])
    )
    bars = (
        alt.Chart(xh)
        .mark_bar(color=MAIN_MID, opacity=0.45, size=11)
        .encode(x=alt.X("小时:Q", bandPosition=0.5), y="首次出现人数:Q", tooltip=["小时", "首次出现人数", "首次出现占比"])
    )
    st.altair_chart(styled(area + bars + line, 330), width="stretch")

    left, right = st.columns([1.15, 1])
    with left:
        sec("从哪来：97% 的人到过和平区", "口径：当天在该区县基站出现过的用户 ÷ 样本用户；分母 5,644 人。")
        dr = q("SELECT district, 到访用户占比 FROM ads_district_reach ORDER BY 到访用户占比 DESC")
        dr["区县"] = dr["district"].str.replace("区", "", n=1)
        dr["标记"] = dr["district"].apply(lambda d: "市核心区" if d in ("和平区", "沈河区", "皇姑区", "铁西区") else "外围")
        bar = (
            alt.Chart(dr)
            .mark_bar(size=15, cornerRadiusEnd=3)
            .encode(
                y=alt.Y("区县:N", sort="-x", title=None, axis=alt.Axis(labelLimit=90)),
                x=alt.X("到访用户占比:Q", axis=alt.Axis(format="%", title="到访用户占比")),
                color=alt.Color(
                    "标记:N",
                    scale=alt.Scale(domain=["市核心区", "外围"], range=[MAIN, MAIN_MID]),
                    legend=None,
                ),
                tooltip=["district", alt.Tooltip("到访用户占比:Q", format=".2%")],
            )
        )
        st.altair_chart(styled(bar, 360), width="stretch")
    with right:
        sec("洗数据：从 53 万到 51 万", "口径：四步顺序清洗，每步剔除记录数与剩余记录数。")
        cs = q("SELECT * FROM ads_clean_steps")
        cs["步骤"] = cs["步骤"].str.replace("缺 imsi / lac / cell", "关键字段缺失")
        step = (
            alt.Chart(cs)
            .mark_bar(color=MAIN, size=22, cornerRadiusEnd=3)
            .encode(
                y=alt.Y("步骤:N", sort=None, title=None),
                x=alt.X("剔除行数:Q", title="剔除记录数"),
                tooltip=["步骤", "剔除行数", "剩余行数", alt.Tooltip("剔除占比:Q", format=".2%")],
            )
        )
        text = step.mark_text(align="left", dx=6, color=MUTED, fontSize=11).encode(text="剔除行数:Q")
        st.altair_chart(styled(step + text, 360).configure_axis(grid=False), width="stretch")
        st.markdown(
            f'<div class="note">总剔除 {n(N_ODS - N_DWD)} 条，其中 84.61% 是“不是 10 月 3 日”的范围筛选；'
            f"质量清洗本身只剔除 2,600 条（0.4880%）。</div>",
            unsafe_allow_html=True,
        )


# ── 2 到访口径 ──────────────────────────────────────────────────────────
def page_caliber() -> None:
    page_head(2, "到访口径", "同一个“来了多少人”，为什么会有 12 个答案——以及我们为什么选其中一个。")
    lo, hi = int(CAL_DF["人数"].min()), int(CAL_DF["人数"].max())
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "当前口径到访人数", n(CUR), f"{radius} 内 · {caliber}", unit="人")
    kpi(c2, "最紧口径", n(lo), "300 米内 · 停留 ≥ 120 分钟", unit="人")
    kpi(c3, "最宽口径", n(hi), "1000 米内 · 任意一条信令", unit="人")
    kpi(c4, "口径差异", f"{hi / lo:.1f}", "同一批人，不同定义", unit="倍")

    st.write("")
    lead(
        "同一个“来了多少人”，在 3 个半径 × 4 种时长口径下有 12 个答案。"
        "半径决定“哪里算西塔”，最短时长决定“什么算来过”。"
        "本系统统一采用 <b>500 米 / 停留 ≥ 30 分钟</b>，并在每处引用时带上这两个参数。"
    )

    sec("12 种口径的矩阵", "行＝半径，列＝最短停留时长；单元格为到访人数。")
    mat = CAL_DF.pivot(index="半径", columns="口径", values="人数").reindex(
        index=["300米", "500米", "1000米"], columns=CALIBER_ORDER
    )
    long = mat.reset_index().melt(id_vars="半径", var_name="口径", value_name="人数")
    heat = (
        alt.Chart(long)
        .mark_rect(cornerRadius=3, stroke="white", strokeWidth=2)
        .encode(
            x=alt.X("口径:N", sort=CALIBER_ORDER, title=None, axis=alt.Axis(labelAngle=0, labelLimit=120)),
            y=alt.Y("半径:N", sort=["300米", "500米", "1000米"], title=None),
            color=alt.Color("人数:Q", scale=alt.Scale(range=["#EAF2F9", "#BBD5E8", MAIN, MAIN_DARK]), legend=None),
            tooltip=["半径", "口径", "人数"],
        )
    )
    label = heat.mark_text(fontSize=14, fontWeight=600).encode(
        text="人数:Q",
        color=alt.condition(alt.datum.人数 > 3300, alt.value("white"), alt.value(MAIN_DARK)),
    )
    st.altair_chart(styled(heat + label, 250).configure_axis(domainColor="white", tickColor="white"), width="stretch")

    left, right = st.columns([1, 1])
    with left:
        sec("同一批人，换口径差 2.9 倍", "口径：ads_caliber_visitors。")
        grp = (
            alt.Chart(CAL_DF)
            .mark_bar(size=16, cornerRadiusEnd=2)
            .encode(
                y=alt.Y("半径:N", sort=["300米", "500米", "1000米"], title=None),
                x=alt.X("人数:Q", title="到访人数"),
                color=alt.Color("口径:N", sort=CALIBER_ORDER, scale=alt.Scale(range=[MAIN_MID, MAIN, "#2A7FB8", MAIN_DARK]), title=None),
                yOffset=alt.YOffset("口径:N", sort=CALIBER_ORDER),
                tooltip=["半径", "口径", "人数"],
            )
        )
        st.altair_chart(styled(grp, 260), width="stretch")
    with right:
        sec("为什么是 500 米与 30 分钟", "口径：半径取自行业常用值，30 分钟来自参数敏感性分析。")
        r = q("SELECT * FROM ads_hotspot_radius")
        r["半径"] = r["半径(米)"].astype(int).astype(str) + " 米"
        ar = (
            alt.Chart(r)
            .mark_line(color=MAIN, strokeWidth=2.6, point=alt.OverlayMarkDef(size=70, filled=True))
            .encode(
                x=alt.X("半径(米):Q", title="半径（米）", scale=alt.Scale(type="log")),
                y=alt.Y("到过的用户占比:Q", axis=alt.Axis(format="%", title="到过的用户占比")),
                tooltip=["半径", alt.Tooltip("到过的用户占比:Q", format=".2%")],
            )
        )
        st.altair_chart(styled(ar, 260), width="stretch")

    st.markdown(
        f'<div class="note">读到 1 公里，“在西塔”就不再区分人：500 米到 1000 米只多 7.71 个百分点，'
        f"往外 4 公里只多 6.07 个百分点。所以本报告用 500 米，并按 30 分钟切停留。</div>",
        unsafe_allow_html=True,
    )


# ── 3 空间口径 ──────────────────────────────────────────────────────────
def page_space() -> None:
    page_head(3, "空间口径", "西塔这个点不是手工标上去的，而是算出来的——换谁都能复现。")
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "热点中心经度", f"{HOTSPOT['lng']:.6f}", f"纬度 {HOTSPOT['lat']:.6f}")
    kpi(c2, "中心取法", "加权重心", "连接用户数前 5 的站点按人数加权")
    kpi(c3, "空间关联率", "99.99845", "51.6 万条记录，仅 8 条未匹配到扇区", unit="%")
    kpi(c4, "覆盖站点", "14,106", "49,948 个扇区键，三扇区站点占 38.09%", unit="个")

    st.write("")
    lead(
        f"西塔是商圈名，不是坐标。项目不手工点位置，而是取当天连接用户数最多的 5 个站点，"
        f"按各自用户数加权求重心，得到 <b>{HOTSPOT['lng']:.6f}、{HOTSPOT['lat']:.6f}</b>，"
        "再把 500 米内的到访视为“来西塔”。换人、换天都能用同一张查询复现。"
    )

    sec("热点与 500 米覆盖", "图：各区县到访用户热力 · 西塔周边站点与 500 米半径。")
    st.image(str(config.IMAGE_DIR / "D4_02_西塔热点.png"), width="stretch")

    left, right = st.columns([1, 1])
    with left:
        sec("半径放大，到过的人有多少", "口径：质心距中心 ≤ 半径的用户 ÷ 样本用户。")
        rr = q("SELECT * FROM ads_hotspot_radius")
        rr["半径"] = rr["半径(米)"].astype(int).astype(str) + " 米"
        rr["折合人数"] = (rr["到过的用户占比"] * N_USERS).round().astype(int)
        b = (
            alt.Chart(rr)
            .mark_bar(cornerRadiusEnd=3, color=MAIN, size=34)
            .encode(
                x=alt.X("半径:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("折合人数:Q", title="到过西塔的人数"),
                tooltip=["半径", "折合人数", alt.Tooltip("到过的用户占比:Q", format=".2%")],
            )
        )
        t = b.mark_text(dy=-8, color=MAIN_DARK, fontSize=12, fontWeight=600).encode(text="折合人数:Q")
        st.altair_chart(styled(b + t, 300).configure_axis(grid=False), width="stretch")
    with right:
        sec("过夜地离西塔有多远", "口径：与 0—6 点重叠 ≥ 60 分钟的最长停留位置，到西塔中心的直线距离。")
        nd = q("SELECT * FROM ads_night_distance")
        nd["半径带"] = nd["过夜地离西塔"]
        nb = (
            alt.Chart(nd)
            .mark_arc(innerRadius=58, outerRadius=105, stroke="white", strokeWidth=2)
            .encode(
                theta=alt.Theta("占比:Q"),
                color=alt.Color("半径带:N", scale=alt.Scale(range=[MAIN_DARK, MAIN, MAIN_MID, GRAY]), legend=alt.Legend(title=None)),
                tooltip=["半径带", alt.Tooltip("占比:Q", format=".2%")],
            )
        )
        st.altair_chart(styled(nb, 260), width="stretch")
        st.markdown(
            '<div class="note">63.91% 的访客能识别过夜地，中位距西塔 2.9 公里；'
            "另有 36.09% 当天 0—6 点没有 ≥ 60 分钟的停留，识别不出夜里在哪。</div>",
            unsafe_allow_html=True,
        )


# ── 4 时间节奏 ──────────────────────────────────────────────────────────
def page_time() -> None:
    page_head(4, "时间节奏", "几点来、几点走：西塔的人流不是慢慢涨上来的，是在 17 点整跳上去的。")
    xh = q("SELECT * FROM ads_xita_hourly ORDER BY 小时")
    peak = xh.loc[xh["在场人数"].idxmax()]
    h16 = int(xh.loc[xh["小时"] == 16, "在场人数"].iloc[0])
    h17 = int(xh.loc[xh["小时"] == 17, "在场人数"].iloc[0])
    first_1719 = int(xh.loc[xh["小时"].between(17, 19), "首次出现人数"].sum())

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "在场峰值", n(peak["在场人数"]), f"{int(peak['小时'])} 点，全天最高", unit="人")
    kpi(c2, "17 点跳变", f"{h17 / h16:.1f}", f"16 点 {n(h16)} 人 → 17 点 {n(h17)} 人", unit="倍")
    kpi(c3, "17—19 点首次到达", n(first_1719), f"占“到过西塔”的 {pc(first_1719 / N_XITA)}", unit="人")
    kpi(c4, "23 点仍在", pc(SHARE_AFTER23, 0), "数据 23:59 截止，时长只能算下限")

    st.write("")
    lead(
        "西塔的一天不是平的：上午 9—16 点稳定在 400 多人，17 点一下跳到 1,254 人，20 点见顶 2,169 人，"
        "23 点仍有 1,820 人。这条曲线是“入场高峰 + 长时间停留”叠加的结果，也是夜间经济最直接的证据。"
    )

    sec("逐时在场与首次出现", "口径：在场＝该小时有信令落在西塔 500 米内；首次＝该小时第一次出现。")
    line = (
        alt.Chart(xh)
        .mark_line(color=MAIN, strokeWidth=2.8, point=alt.OverlayMarkDef(size=55, filled=True))
        .encode(
            x=alt.X("小时:Q", axis=alt.Axis(values=list(range(0, 24, 2)), title="时刻（时）"), scale=alt.Scale(domain=[0, 23])),
            y=alt.Y("在场人数:Q", title="人数"),
            tooltip=["小时", "在场人数", "首次出现人数", alt.Tooltip("首次出现占比:Q", format=".2%")],
        )
    )
    bars = (
        alt.Chart(xh)
        .mark_bar(color=MAIN_MID, opacity=0.5, size=13)
        .encode(x=alt.X("小时:Q", bandPosition=0.5), y="首次出现人数:Q")
    )
    rule = (
        alt.Chart(pd.DataFrame({"y": [h16, h17]}))
        .mark_rule(color=ORANGE, strokeDash=[4, 4], strokeWidth=1.2)
        .encode(y="y:Q")
    )
    st.altair_chart(styled(bars + line + rule, 340), width="stretch")

    left, right = st.columns([1.05, 1])
    with left:
        sec("越晚到，越可能跨过 23 点", "口径：按首次到达小时分组，23:00 后仍在西塔的占比。")
        cn = q("SELECT * FROM ads_xita_censoring")
        cn["到达"] = cn["首次到达小时"].astype(int).astype(str) + " 点"
        cb = (
            alt.Chart(cn)
            .mark_bar(color=MAIN, cornerRadiusEnd=3, size=26)
            .encode(
                x=alt.X("到达:N", sort=None, title="首次到达西塔的时刻", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("23点后扔在的占比:Q", axis=alt.Axis(format="%", title="23 点后仍在的占比")),
                tooltip=["到达", alt.Tooltip("23点后扔在的占比:Q", format=".2%")],
            )
        )
        ct = cb.mark_text(dy=-8, color=MAIN_DARK, fontSize=12, fontWeight=600).encode(
            text=alt.Text("23点后扔在的占比:Q", format=".0%")
        )
        st.altair_chart(styled(cb + ct, 300).configure_axis(grid=False), width="stretch")
    with right:
        sec("停留时长的右删失", "口径：数据在 23:59 截止，之后无法观测，因此所有时长都是下限。")
        st.markdown(
            f"""
<div style="font-size:14px;line-height:2.05;color:{INK}">
17 点到的人里只有 <b>{pc(cn.loc[cn['首次到达小时'] == 17, '23点后扔在的占比'].iloc[0], 1)}</b> 跨过 23 点，
20 点到的是 <b>{pc(cn.loc[cn['首次到达小时'] == 20, '23点后扔在的占比'].iloc[0], 1)}</b>，
22 点到的 <b>{pc(cn.loc[cn['首次到达小时'] == 22, '23点后扔在的占比'].iloc[0], 1)}</b> 会跨过去。
<br><br>
所以本系统一律写“<b>至少 {hours(MED_STAY)} 小时</b>”，不写“平均停留 {hours(MED_STAY)} 小时”——
前者是数据能证明的，后者不是。要得到真实时长，需要把次日 0—6 点的信令接上。
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="note">图上那条虚线是全部傍晚访客的 41%：整体有 41% 的人到 23 点仍在。</div>',
            unsafe_allow_html=True,
        )


# ── 5 停留识别 ──────────────────────────────────────────────────────────
def page_stay() -> None:
    page_head(5, "停留识别", "怎样把 51 万条零散信令，压成 1.9 万个“待了多久”的停留。")
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "识别停留", n(N_STAY), "质心 ≤ 500 米、持续 ≥ 30 分钟", unit="个")
    kpi(c2, "压缩比", f"{N_DWD / N_STAY:.0f}", "51 万条信令 → 1.9 万个停留", unit=": 1")
    kpi(c3, "有停留的用户", n(N_STAY_USER), f"占样本 {pc(N_STAY_USER / N_USERS)}，人均 {N_STAY / N_USERS:.2f} 个", unit="人")
    kpi(c4, "中位停留", f"{MED_STAY:.0f}", f"约 {hours(MED_STAY)} 小时，右删失下限", unit="分钟")

    st.write("")
    lead(
        "停留不是“一条信令停在那里”，而是按时间扫描出的一段：下一条记录离段质心不超过 500 米就并入，"
        "超过就另开一段；持续不少于 30 分钟的段才算停留。半径吸收乒乓切换，时长区分“停下来过”和“路过”。"
    )

    left, right = st.columns([1, 1])
    with left:
        sec("停留时长分布（傍晚访客）", "口径：dws_visitor.xita_stay_min，按小时分箱。")
        bins = [0, 15, 30, 60, 90, 120, 180, 240, 300, 400, 1440]
        hb = pd.cut(VISITOR["xita_stay_min"], bins=bins, right=False)
        dist = hb.value_counts().sort_index().rename_axis("区间").reset_index(name="人数")
        dist["区间"] = dist["区间"].astype(str).str.replace("[", "").str.replace(")", "").str.replace(", ", "—")
        bb = (
            alt.Chart(dist)
            .mark_bar(color=MAIN, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("区间:N", sort=None, title="停留时长（分钟）", axis=alt.Axis(labelAngle=-40, labelLimit=90)),
                y=alt.Y("人数:Q", title="人数"),
                tooltip=["区间", "人数"],
            )
        )
        st.altair_chart(styled(bb, 300).configure_axis(grid=False), width="stretch")
    with right:
        sec("四类客群的停留中位", "口径：dws_visitor，中位数为组内中位数，不按人数加权。")
        seg = q("SELECT * FROM ads_visitor_segment")
        sb = (
            alt.Chart(seg)
            .mark_bar(size=22, cornerRadiusEnd=3)
            .encode(
                y=alt.Y("客群:N", sort="-x", title=None),
                x=alt.X("西塔停留中位_分:Q", title="停留中位（分钟）"),
                color=alt.Color("客群:N", scale=alt.Scale(
                    domain=list(SEG_COLOR), range=list(SEG_COLOR.values())), legend=None),
                tooltip=["客群", "人数", "西塔停留中位_分", "首次到达中位_时"],
            )
        )
        st.altair_chart(styled(sb, 300), width="stretch")
        st.markdown(
            '<div class="note">周边居民的 620.8 分钟不是“到访”，是他们整天就在这一带——'
            "停留识别把居家时间也算成了“在西塔的停留”。</div>",
            unsafe_allow_html=True,
        )

    sec("参数敏感性：半径不敏感，时长敏感", "口径：ads_stay_sensitivity，25 组参数组合，纵轴为人均停留点个数。")
    sens = q("SELECT * FROM ads_stay_sensitivity")
    sens["最短时长"] = sens["最短时长(分)"].astype(int).astype(str) + " 分钟"
    sens["半径"] = sens["半径(米)"].astype(int).astype(str) + " 米"
    hm = (
        alt.Chart(sens)
        .mark_rect(cornerRadius=2, stroke="white", strokeWidth=2)
        .encode(
            x=alt.X("半径:N", sort=None, title="切段半径", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("最短时长:N", sort=None, title="最短停留时长"),
            color=alt.Color("人均停留点:Q", scale=alt.Scale(range=["#EAF2F9", MAIN, MAIN_DARK]), legend=None),
            tooltip=["半径", "最短时长", "人均停留点"],
        )
    )
    hmt = hm.mark_text(fontSize=12, fontWeight=600).encode(
        text=alt.Text("人均停留点:Q", format=".2f"),
        color=alt.condition(alt.datum.人均停留点 > 4.6, alt.value("white"), alt.value(MAIN_DARK)),
    )
    st.altair_chart(styled(hm + hmt, 300).configure_axis(domainColor="white", tickColor="white"), width="stretch")
    st.markdown(
        '<div class="note">半径 300 米到 1 公里，人均停留点只差 0.2 左右；最短时长从 5 分钟拉到 60 分钟，'
        "人均停留点从 5.33 个掉到 2.66 个。所以“30 分钟”必须写进每一处口径说明，而半径可以略说。"
        "</div>",
        unsafe_allow_html=True,
    )


# ── 6 客群构成 ──────────────────────────────────────────────────────────
def page_segment() -> None:
    page_head(6, "客群构成", "来的是谁：本市、周边、外地，还是根本判断不出夜里在哪。")
    seg = q("SELECT * FROM ads_visitor_segment")
    total = int(seg["人数"].sum())
    c1, c2, c3, c4 = st.columns(4)
    for col, (name, color) in zip((c1, c2, c3, c4), [("市内来访", ""), ("周边居民", ""), ("外地来客", ""), ("过夜地不明", "")]):
        row = seg[seg["客群"] == name].iloc[0]
        kpi(col, name, n(row["人数"]), f"{pc(row['占比'])} · 停留中位 {row['西塔停留中位_分']:.0f} 分钟", unit="人")

    st.write("")
    lead(
        "分群用规则而不是聚类，因为规则能解释、能复核、能交给甲方自己算。"
        "判断顺序是：先判“过夜地不明”（0—6 点没有 ≥ 60 分钟停留），再判“外地来客”"
        "（过夜地在市域外，或当天首条信令在市外、之后入城），再判“周边居民”（过夜地距西塔 < 1.5 公里），"
        "剩下的都是“市内来访”。"
    )

    left, right = st.columns([1.1, 1])
    with left:
        sec("四类客群（第二版口径）", "口径：dws_visitor_tag.segment_v2，分母为 3,310 名傍晚访客。")
        sb = (
            alt.Chart(seg)
            .mark_bar(size=34, cornerRadiusEnd=4)
            .encode(
                x=alt.X("人数:Q", title="人数"),
                y=alt.Y("客群:N", sort="-x", title=None),
                color=alt.Color("客群:N", scale=alt.Scale(
                    domain=list(SEG_COLOR), range=list(SEG_COLOR.values())), legend=None),
                tooltip=["客群", "人数", alt.Tooltip("占比:Q", format=".2%"), "西塔停留中位_分"],
            )
        )
        st.altair_chart(styled(sb, 300), width="stretch")
    with right:
        sec("到访时刻：都在傍晚，居民例外", "口径：首次到达西塔的时刻，组内中位数。")
        tb = (
            alt.Chart(seg)
            .mark_circle(size=200, opacity=0.9)
            .encode(
                x=alt.X("首次到达中位_时:Q", title="首次到达（时）", scale=alt.Scale(domain=[0, 24]),
                        axis=alt.Axis(values=[0, 6, 12, 18, 24])),
                y=alt.Y("西塔停留中位_分:Q", title="停留中位（分钟）"),
                color=alt.Color("客群:N", scale=alt.Scale(
                    domain=list(SEG_COLOR), range=list(SEG_COLOR.values())), legend=None),
                tooltip=["客群", "首次到达中位_时", "西塔停留中位_分"],
            )
        )
        st.altair_chart(styled(tb, 300), width="stretch")
        st.markdown(
            '<div class="note">三个“访客”类（市内、外地、不明）行为几乎一致：傍晚 18:45—19:30 到，待 2.2—2.4 小时。</div>',
            unsafe_allow_html=True,
        )

    sec("口径修正：外地来客从 1% 到 14%", "原因：只用“过夜地在哪”会漏掉当天才进城的人——他们凌晨还在外地，信令不在样本内。")
    st.image(str(config.IMAGE_DIR / "D8_02_外地来客口径修正.png"), width="stretch")
    st.markdown(
        '<div class="note">第一版只用过夜地分群，外地来客只有 31 人（0.94%）；加上“当天首条信令在市域外、之后入城”'
        "这条独立证据后，外地来客变成 473 人（14.29%），其中 436 人原来落在“过夜地不明”。"
        "</div>",
        unsafe_allow_html=True,
    )


# ── 7 商圈联动 ──────────────────────────────────────────────────────────
def page_link() -> None:
    page_head(7, "商圈联动", "还去了哪：太原街是西塔最主要的上游，中街弱一个量级——而且方向基本单向。")
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "先到太原街", n(TAIYUAN_UP_N), f"占访客 {pc(TAIYUAN_SHARE, 1)}，到西塔前停留 ≥ 30 分钟", unit="人")
    kpi(c2, "间隔中位", GAP_TAIYUAN, "离开太原街到抵达西塔", unit="分钟")
    kpi(c3, "先到中街", n(ZHONGJIE_UP_N), f"占访客 {pc(ZHONGJIE_SHARE, 1)}，间隔 {GAP_ZHONGJIE} 分钟", unit="人")
    kpi(c4, "西塔之后再去", n(TAIYUAN_AFTER),
        f"是回中街（{n(ZHONGJIE_AFTER)} 人）的 {TAIYUAN_AFTER / ZHONGJIE_AFTER:.1f} 倍", unit="人")

    st.write("")
    lead(
        "把每个访客在西塔以外的停留按“到达前 / 离开后”切开，就能看出联动方向："
        "太原街是最大的上游商圈（15.0%），离开西塔后再去太原街的只有 7.0%——"
        "这是一条现成的、单向的客流通道；中街则弱一个量级。"
    )

    lk = q("SELECT * FROM ads_xita_linkage")
    left, right = st.columns([1, 1])
    with left:
        sec("到达西塔前后的商圈停留", "口径：一人可属多类，各行占比不可相加。")
        lk2 = lk.melt(id_vars="地点", value_vars=["之前人数", "之后人数"], var_name="方向", value_name="人数")
        lk2["方向"] = lk2["方向"].str.replace("之前人数", "到西塔前").str.replace("之后人数", "离开西塔后")
        lb = (
            alt.Chart(lk2)
            .mark_bar(size=20, cornerRadiusEnd=3)
            .encode(
                y=alt.Y("地点:N", sort=None, title=None),
                x=alt.X("人数:Q", title="人数"),
                color=alt.Color("方向:N", scale=alt.Scale(domain=["到西塔前", "离开西塔后"], range=[MAIN, MAIN_MID]), title=None),
                yOffset=alt.YOffset("方向:N", sort=["到西塔前", "离开西塔后"]),
                tooltip=["地点", "方向", "人数"],
            )
        )
        st.altair_chart(styled(lb, 300), width="stretch")
    with right:
        sec("三个商圈的一天", "口径：逐小时在该商圈 500 米内出现过的用户数。")
        zh = q("SELECT * FROM ads_zone_hourly ORDER BY 小时")
        zh_long = zh.melt(id_vars="小时", value_vars=list(AREA_COLOR), var_name="商圈", value_name="人数")
        zl = (
            alt.Chart(zh_long)
            .mark_line(strokeWidth=2.4)
            .encode(
                x=alt.X("小时:Q", title="时刻（时）", scale=alt.Scale(domain=[0, 23]),
                        axis=alt.Axis(values=list(range(0, 24, 3)))),
                y=alt.Y("人数:Q", title="在场人数"),
                color=alt.Color("商圈:N", scale=alt.Scale(
                    domain=list(AREA_COLOR), range=list(AREA_COLOR.values())), title=None),
                tooltip=["商圈", "小时", "人数"],
            )
        )
        st.altair_chart(styled(zl, 300), width="stretch")
        st.markdown(
            '<div class="note">西塔 17 点起陡增；太原街全天缓慢上行、21 点仍有 425 人；'
            "中街 11—16 点爬升后晚上回落——三条曲线形状完全不同。</div>",
            unsafe_allow_html=True,
        )

    sec("联动怎么读：方向不是因果", "数据只能说明“同一天里既去了 A 又去了 B”，不能说明被 A 吸引。")
    two_col(
        ("可以说", GREEN, [
            f"{pc(TAIYUAN_SHARE, 1)} 的访客到西塔前在太原街停留，中位间隔 {GAP_TAIYUAN} 分钟",
            f"离开西塔后再去太原街的人只有 {pc(TAIYUAN_AFTER / N_VISITOR, 1)}，方向基本单向",
            f"中街的联动弱一个量级（{pc(ZHONGJIE_SHARE, 1)} / {pc(35 / N_VISITOR, 1)}）",
        ]),
        ("不能说", AMBER, [
            "“太原街把客人送到了西塔”——先后顺序不是因果",
            "“西塔的客人会再去太原街消费”——没有消费数据",
            "“两个商圈联动密切”后面必须跟口径，否则读者会当成客流互导率",
        ]),
    )


# ── 8 工程与边界 ────────────────────────────────────────────────────────
def page_engineering() -> None:
    page_head(8, "工程与边界", "这些数字能不能每天重跑、能不能追溯，以及对外到底能说多大话。")
    _xh = q("SELECT * FROM ads_xita_hourly ORDER BY 小时")
    _h16 = int(_xh.loc[_xh["小时"] == 16, "在场人数"].iloc[0])
    _h17 = int(_xh.loc[_xh["小时"] == 17, "在场人数"].iloc[0])
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "流水线", len(ETL), f"最新批次 {LAST_BATCH}", unit="步")
    kpi(c2, "单批耗时", f"{ETL['耗时(秒)'].sum():.1f}", "本地库、单机，一条命令跑完", unit="秒")
    kpi(c3, "质量稽核", "16", "通过 5 / 警告 6 / 不通过 5", unit="项")
    kpi(c4, "测试基线", "78", "含真实库结构对账，约 1.1 秒", unit="项")

    st.write("")
    lead(
        "这套数字每天能重跑一遍：ODS 接入 → 清洗 → 明细 → 维表 → 停留 → 汇总，十步写进运行日志，"
        "带同一个批次号。任何时候都能回答“这张表是哪次跑出来的、当时有多少行”。"
    )

    left, right = st.columns([1.05, 1])
    with left:
        sec("流水线各步骤的输入输出与耗时", f"口径：etl_log 批次 {LAST_BATCH}。空值表示该步骤只读文件、不接上游表。")
        rows, tot_in, tot_out, tot_s = [], 0, 0, 0.0
        for _, r in ETL.iterrows():
            i_in = "—" if pd.isna(r["输入行数"]) else n(r["输入行数"])
            i_out = "—" if pd.isna(r["输出行数"]) else n(r["输出行数"])
            if not pd.isna(r["输入行数"]):
                tot_in += int(r["输入行数"])
            if not pd.isna(r["输出行数"]):
                tot_out += int(r["输出行数"])
            tot_s += float(r["耗时(秒)"])
            rows.append([r["步骤"], i_in, i_out, f"{r['耗时(秒)']:.2f}"])
        html_table(
            ["步骤", "输入行数", "输出行数", "耗时（秒）"],
            rows,
            total=["合计", n(tot_in), n(tot_out), f"{tot_s:.2f}"],
            aligns=["l", "r", "r", "r"],
        )
    with right:
        sec("质量稽核：7 个维度的结论", "口径：dq_check_result，按检查项计数，不按严重度加权。")
        dq = q("SELECT * FROM ads_dq_summary")
        dq_long = dq.melt(id_vars="维度", value_vars=["不通过", "警告", "通过"], var_name="状态", value_name="项数")
        dqb = (
            alt.Chart(dq_long)
            .mark_bar(size=18, cornerRadiusEnd=2)
            .encode(
                y=alt.Y("维度:N", sort=None, title=None),
                x=alt.X("项数:Q", title="检查项数"),
                color=alt.Color("状态:N", scale=alt.Scale(
                    domain=["不通过", "警告", "通过"], range=[RED, AMBER, GRAY]), title=None),
                order=alt.Order("状态:N", sort="ascending"),
                tooltip=["维度", "状态", "项数"],
            )
        )
        st.altair_chart(styled(dqb, 372), width="stretch")

    sec("能说的话与不能说的话", "对外发布只用左列句式；写右列必须补上限定语或注明来源口径。")
    two_col(
        ("可以这样写", GREEN, [
            f"样本内 {n(N_VISITOR)} 人到访西塔（500 米 / ≥30 分钟）",
            f"停留中位至少 {hours(MED_STAY)} 小时",
            f"{pc(SHARE_AFTER23, 0)} 的访客 23 点仍在西塔",
            f"17 点在场人数是 16 点的 {_h17 / _h16:.1f} 倍",
            "外地来客占样本的 14.29%",
        ]),
        ("不能这样写", AMBER, [
            f"西塔国庆当天客流 {n(N_VISITOR)} 人",
            f"客人平均停留 {hours(MED_STAY)} 小时",
            "四成客人会过夜",
            "西塔每天 17 点开始上人",
            "外地游客占一成五",
        ]),
    )

    sec("数据与口径声明")
    _decl = [
        ("样本", f"{config.SOURCE_NOTE}，业务日期 {config.ANALYSIS_DAY}，共 {n(N_DWD)} 条明细、"
                 f"{n(N_USERS)} 个完整标识。"),
        ("口径", "西塔＝加权热点中心 500 米；到访＝半径内停留 ≥ 30 分钟；"
                 "停留＝质心 ≤ 500 米且持续 ≥ 30 分钟。"),
        ("边界", "只覆盖中国移动用户、只有一天、样本按“到过西塔”圈选——"
                 "不能推算全市人数、不能做同比、不能算渗透率。"),
        ("合规", "页面只展示聚合结果，不含任何用户标识；明细数据不对外、不进展示层。"),
    ]
    st.markdown(
        '<div style="border:1px solid var(--line);background:var(--card);padding:2px 20px">'
        + "".join(
            f'<div style="display:grid;grid-template-columns:64px 1fr;gap:16px;padding:13px 0;'
            f'{"border-bottom:1px solid var(--line2)" if i < len(_decl) - 1 else ""}">'
            f'<div style="font-size:10px;letter-spacing:.14em;color:var(--faint);padding-top:3px">{k}</div>'
            f'<div style="font-size:12.5px;line-height:1.9;color:var(--ink2)">{v}</div></div>'
            for i, (k, v) in enumerate(_decl)
        )
        + "</div>",
        unsafe_allow_html=True,
    )


# ── 路由 ────────────────────────────────────────────────────────────────
ROUTES = {
    "概览": page_overview,
    "到访口径": page_caliber,
    "空间口径": page_space,
    "时间节奏": page_time,
    "停留识别": page_stay,
    "客群构成": page_segment,
    "商圈联动": page_link,
    "工程与边界": page_engineering,
}
if page == "概览":
    page_overview()
else:
    topbar()
    ROUTES[page]()

st.markdown(
    f'<div class="foot">{config.SOURCE_NOTE}　|　业务日期 {config.ANALYSIS_DAY}　|　'
    f"口径：500 米 / 停留 ≥ 30 分钟　|　运行批次 {LAST_BATCH}　|　"
    f"展示层仅含聚合结果，不含用户标识　|　页面生成于 {datetime.now():%Y-%m-%d %H:%M}</div>",
    unsafe_allow_html=True,
)
