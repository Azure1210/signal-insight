#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""构建《沈阳移动信令数据分析报告》（分析版）。

版式与样式参照：报告攥写/沈阳移动信令数据质量分析报告_企业评审版_20261015.docx
内容来自 notebook D1—D8 的分析结果：data/signal.db 中的 ads_* / dws_* 表，
图表来自 image/ 目录。

目录页码由两遍生成得到：
  1) python 报告攥写\\build_analysis_report.py         # 第一遍，目录页码取 .pagemap.json（缺失写 0）
  2) libreoffice-kit convert 转 PDF
  3) python 报告攥写\\pagemap.py                       # 从 PDF 反查每个标题所在页，写 .pagemap.json
  4) python 报告攥写\\build_analysis_report.py         # 第二遍，页码回填
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor, Twips
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "报告攥写"
REF = REPORT_DIR / "沈阳移动信令数据质量分析报告_企业评审版_20261015.docx"
OUT = REPORT_DIR / "沈阳移动信令数据分析报告_分析版_20261019.docx"
IMG = ROOT / "image"
DB = ROOT / "data" / "signal.db"
PAGEMAP = REPORT_DIR / ".pagemap.json"

DOC_NO = "DA-SY-20181003"
HEADER_TITLE = "沈阳移动信令数据分析报告"
MAX_W = 15.8
MAX_H = 10.4
TEXT_W = 9071  # twips，与页面正文宽度一致（11906 - 1417*2）

con = sqlite3.connect(DB)


def sql(q):
    return pd.read_sql(q, con)


def n(x):
    return f"{x:,.0f}" if float(x) == int(x) else f"{x:,.2f}"


def pc(x, d=2):
    return f"{x * 100:.{d}f}%"


# ── 数据 ────────────────────────────────────────────────────────────────
DAILY = sql("SELECT * FROM ads_daily_volume ORDER BY 日期")
REACH = sql("SELECT * FROM ads_district_reach ORDER BY 到访用户占比 DESC")
HOT_R = sql('SELECT "半径(米)" AS r, "到过的用户占比" AS p FROM ads_hotspot_radius ORDER BY "半径(米)"')
CALIBER = sql("SELECT 半径, 口径, 人数 FROM ads_caliber_visitors")
ZONE = sql("SELECT * FROM ads_zone_hourly ORDER BY 小时")
XITA_H = sql("SELECT * FROM ads_xita_hourly ORDER BY 小时").set_index("小时")
CENSOR = sql("SELECT * FROM ads_xita_censoring ORDER BY 首次到达小时")
NIGHT_D = sql("SELECT 过夜地离西塔 AS band, 占比 AS p FROM ads_night_distance")
NIGHT_DIST = sql("SELECT night_district, COUNT(*) n FROM dws_night GROUP BY 1 ORDER BY n DESC")
SEG = sql("SELECT * FROM ads_visitor_segment ORDER BY 人数 DESC")
# D08 第一版分群（只按过夜地）：人数从库里数，中位数取自 D08 输出
V1 = sql("SELECT segment AS 客群, COUNT(*) AS 人数 FROM dws_visitor_tag GROUP BY 1 ORDER BY 人数 DESC")
V1_TOTAL = int(V1["人数"].sum())
V1_MED = {
    "市内来访": (144.1, 18.76),
    "过夜地不明": (139.4, 18.75),
    "周边居民": (620.4, 1.00),
    "市外来访": (130.0, 19.46),
}
LINK = sql("SELECT * FROM ads_xita_linkage")
SENS = sql("SELECT * FROM ads_stay_sensitivity")
CLEAN = sql("SELECT * FROM ads_clean_steps")
DQ = sql("SELECT * FROM dq_check_result ORDER BY check_id")
ETL = sql("SELECT * FROM etl_log WHERE 批次 = (SELECT MAX(批次) FROM etl_log) ORDER BY rowid")

N_ODS = int(sql("SELECT COUNT(*) n FROM ods_signal")["n"][0])
N_DWD = int(sql("SELECT COUNT(*) n FROM dwd_signal")["n"][0])
N_USERS = int(sql("SELECT COUNT(DISTINCT imsi) n FROM dwd_signal")["n"][0])
N_STAY = int(sql("SELECT COUNT(*) n FROM dws_stay")["n"][0])
N_STAY_USER = int(sql("SELECT COUNT(DISTINCT imsi) n FROM dws_stay")["n"][0])
N_VISITOR = int(sql("SELECT COUNT(*) n FROM dws_visitor")["n"][0])
N_NIGHT = int(sql("SELECT COUNT(*) n FROM dws_night")["n"][0])
N_HOUR = int(sql("SELECT COUNT(*) n FROM dws_user_hour")["n"][0])
N_XITA = int(CALIBER[(CALIBER["半径"] == "500米") & (CALIBER["口径"] == "停留>=30分钟")]["人数"].iloc[0])
N_ANY500 = int(CALIBER[(CALIBER["半径"] == "500米") & (CALIBER["口径"] == "任意一条信令")]["人数"].iloc[0])
N_HOT5 = int(N_XITA)
ETA_TOTAL = float(ETL["耗时(秒)"].sum())
N_AFTER23 = 0.41

doc = Document(str(REF))
body = doc.element.body
for child in list(body.iterchildren()):
    if child.tag != qn("w:sectPr"):
        body.remove(child)

# 页眉沿用参照文档：右对齐、下方细线、8.5pt；只换文字，不动格式
for sec in doc.sections:
    for hdr in (sec.header, sec.first_page_header):
        for hp in hdr.paragraphs:
            runs = [r for r in hp.runs if r.text.strip()]
            if not runs:
                continue
            runs[0].text = HEADER_TITLE
            if len(runs) > 1:
                runs[1].text = "    " + DOC_NO
                for extra in runs[2:]:
                    extra.text = ""
            else:
                runs[0].text = HEADER_TITLE + "    " + DOC_NO


# ── 基础构件 ────────────────────────────────────────────────────────────
def _txt(p, text, bold=False, size=None, color=None, italic=False):
    r = p.add_run(text)
    if bold:
        r.font.bold = True
    if italic:
        r.font.italic = True
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    return r


def spacer():
    doc.add_paragraph(style="DQSpacer")


def body_p(text, indent=True, space_before=None, space_after=None):
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.first_line_indent = Twips(440)
    if space_before is not None:
        p.paragraph_format.space_before = Pt(space_before)
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    _txt(p, text)
    return p


def lead_p(text, size=None):
    """整段加粗的结论句。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    _txt(p, text, bold=True, size=size)
    return p


PENDING_BREAK = [False]


def h1(text):
    p = doc.add_paragraph(style="Heading1")
    if PENDING_BREAK[0]:
        p.paragraph_format.page_break_before = True
        PENDING_BREAK[0] = False
    else:
        p.paragraph_format.space_before = Pt(22)
    _txt(p, text)
    return p


def h2(text):
    p = doc.add_paragraph(style="Heading2")
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(14)
    _txt(p, text)
    return p


def note(text):
    p = doc.add_paragraph(style="DQNote")
    _txt(p, text)
    return p


def page_break():
    """让下一个一级标题从新页开始，不留下空段落。"""
    PENDING_BREAK[0] = True


FIG_N = [0]
TAB_N = [0]


def figure(img_name, caption, source, width=None):
    FIG_N[0] += 1
    path = IMG / img_name
    w = Image.open(path).size
    ar = w[1] / w[0]
    width = width or min(MAX_W, MAX_H / ar)
    p = doc.add_paragraph(style="DQFigure")
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width))
    cap = doc.add_paragraph(style="DQCaption")
    _txt(cap, f"图 {FIG_N[0]}  {caption}")
    src = doc.add_paragraph(style="DQSource")
    _txt(src, f"口径与来源：{source}")
    return FIG_N[0]


def _tc(tc, text, width_cm, fill, bold=False, white=False, size=11, align="center"):
    """填一个单元格：底色、内边距、垂直居中、DQTable 段落。"""
    tc.width = Cm(width_cm)
    tcPr = tc._tc.get_or_add_tcPr()

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)

    mar = OxmlElement("w:tcMar")
    for side, val in (("top", "80"), ("left", "95"), ("bottom", "80"), ("right", "95")):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), val)
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tcPr.append(mar)

    va = OxmlElement("w:vAlign")
    va.set(qn("w:val"), "center")
    tcPr.append(va)

    p = tc.paragraphs[0]
    p.style = doc.styles["DQTable"]
    p.paragraph_format.keep_together = True
    p.paragraph_format.line_spacing = 1.2
    p.alignment = {"center": WD_ALIGN_PARAGRAPH.CENTER, "left": WD_ALIGN_PARAGRAPH.LEFT}[align]
    r = _txt(p, str(text), bold=bold, size=size)
    if white:
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def table(caption, header, rows, widths, first_left=False, size=11, cap=None):
    TAB_N[0] += 1
    cap_p = doc.add_paragraph(style="DQCaption")
    cap_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cap_p.paragraph_format.keep_with_next = True
    _txt(cap_p, cap or f"表 {TAB_N[0]}  {caption}")

    t = doc.add_table(rows=len(rows) + 1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False

    tblPr = t._tbl.tblPr
    for child in list(tblPr):
        tblPr.remove(child)
    tw = OxmlElement("w:tblW")
    tw.set(qn("w:w"), str(TEXT_W))
    tw.set(qn("w:type"), "dxa")
    tblPr.append(tw)
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    tblPr.append(jc)
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "D9D9D9")
        borders.append(e)
    tblPr.append(borders)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    cm = OxmlElement("w:tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), "85")
        e.set(qn("w:type"), "dxa")
        cm.append(e)
    tblPr.append(cm)

    # 列宽
    scale = TEXT_W / (sum(widths) / 2.54 * 1440)
    for i, w_cm in enumerate(widths):
        t.columns[i].width = Cm(w_cm * scale)

    for c, text in enumerate(header):
        _tc(t.rows[0].cells[c], text, widths[c] * scale, "214F70", bold=True, white=True, size=size)
    trPr = t.rows[0]._tr.get_or_add_trPr()
    e = OxmlElement("w:cantSplit")
    trPr.append(e)
    e = OxmlElement("w:tblHeader")
    trPr.append(e)
    e = OxmlElement("w:jc")
    e.set(qn("w:val"), "center")
    trPr.append(e)

    for r, row in enumerate(rows, start=1):
        fill = "FFFFFF" if r % 2 == 1 else "F0F4F7"
        for c, text in enumerate(row):
            _tc(
                t.rows[r].cells[c],
                text,
                widths[c] * scale,
                fill,
                size=size,
                align=("left" if (first_left and c == 0) else "center"),
            )
        trPr = t.rows[r]._tr.get_or_add_trPr()
        e = OxmlElement("w:cantSplit")
        trPr.append(e)
        e = OxmlElement("w:jc")
        e.set(qn("w:val"), "center")
        trPr.append(e)

    # 让整张表尽量不跨页：除最后一行外，单元格段落都 keepNext
    for row in t.rows[:-1]:
        for cell in row.cells:
            for cp in cell.paragraphs:
                cp.paragraph_format.keep_with_next = True

    spacer()
    return TAB_N[0]


def toc_entry(text, page, level=1):
    p = doc.add_paragraph(style="toc 1" if level == 1 else "toc 2")
    pf = p.paragraph_format
    pf.left_indent = Twips(0 if level == 1 else 320)
    pf.space_after = Pt(0)
    pf.line_spacing = Pt(16)
    pf.keep_together = True
    pf.tab_stops.add_tab_stop(Twips(9062), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    _txt(p, text, size=10.5)
    p.add_run("\t")
    _txt(p, str(page), size=10.5)
    return p


def cover_table(header, values, widths):
    t = doc.add_table(rows=2, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    tblPr = t._tbl.tblPr
    for child in list(tblPr):
        tblPr.remove(child)
    tw = OxmlElement("w:tblW")
    tw.set(qn("w:w"), str(TEXT_W))
    tw.set(qn("w:type"), "dxa")
    tblPr.append(tw)
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    tblPr.append(jc)
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "D9D9D9")
        borders.append(e)
    tblPr.append(borders)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    cm = OxmlElement("w:tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), "85")
        e.set(qn("w:type"), "dxa")
        cm.append(e)
    tblPr.append(cm)

    scale = TEXT_W / (sum(widths) / 2.54 * 1440)
    for i, w_cm in enumerate(widths):
        t.columns[i].width = Cm(w_cm * scale)
    for c, text in enumerate(header):
        _tc(t.rows[0].cells[c], text, widths[c] * scale, "214F70", bold=True, white=True)
    for c, text in enumerate(values):
        _tc(t.rows[1].cells[c], text, widths[c] * scale, "FFFFFF")
    for row in t.rows:
        trPr = row._tr.get_or_add_trPr()
        e = OxmlElement("w:cantSplit")
        trPr.append(e)
        e = OxmlElement("w:jc")
        e.set(qn("w:val"), "center")
        trPr.append(e)
    return t


def page_of(key, default=0):
    if PAGEMAP.exists():
        return json.loads(PAGEMAP.read_text(encoding="utf-8")).get(key.replace(" ", ""), default)
    return default


# ── 封面 ────────────────────────────────────────────────────────────────
p = doc.add_paragraph(style="Subtitle")
p.paragraph_format.space_before = Pt(28)
p.paragraph_format.space_after = Pt(54)
_txt(p, "分析与业务洞察")

for line in ("沈阳移动信令", "数据分析报告"):
    p = doc.add_paragraph(style="Title")
    p.paragraph_format.space_after = Pt(16)
    p.paragraph_format.line_spacing = 1.35
    _txt(p, line)

p = doc.add_paragraph(style="Subtitle")
p.paragraph_format.space_after = Pt(24)
_txt(p, "SHENYANG MOBILE SIGNALING  VISITOR ANALYSIS", size=10)

p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(22)
_txt(p, "2018 年 10 月 3 日样本", bold=True, size=15)

p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(28)
_txt(p, "从 53 万条信令还原国庆傍晚来西塔的人：几点来、待多久、从哪来、还去了哪。")

cover_table(
    ["傍晚访客", "识别停留", "西塔停留中位"],
    ["3,310 人", "19,015 个", "至少 2.7 小时"],
    [3.1, 2.6, 3.4],
)
spacer()

lead_p("分析结论  口径内可用", size=13)
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(24)
_txt(
    p,
    "适用于该单日、该运营商、该圈选样本的聚合描述；人数、时长与来源均按样本内口径给出，"
    "属于下限而不是全市实际值。",
    size=10.5,
)

cover_table(
    ["文档编号", "版本及用途", "编制日期"],
    [DOC_NO, "V1.0  分析版", "2026 年 10 月 19 日"],
    [3.1, 2.6, 3.4],
)
spacer()

note("样本为历史脱敏数据；报告中的一切人数均为中国移动用户样本内口径，不等于西塔客流，也不等于全市人流。")

p = doc.add_paragraph(style="TOCHeading")
p.paragraph_format.page_break_before = True
p.paragraph_format.space_before = Pt(0)
_txt(p, "阅读导航")
p = doc.add_paragraph()
_txt(
    p,
    "决策者可先读管理摘要与第 13 章；业务与运营人员宜结合第 4—11 章的口径看数；"
    "口径参数与证据的完整索引见附录 A。",
    size=10.5,
)

TOC = [
    (1, "管理摘要"),
    (1, "1  分析问题与口径"),
    (1, "2  数据与样本"),
    (1, "3  空间口径：热点、半径与商圈"),
    (1, "4  到访人数：一个数字，十二种口径"),
    (2, "4.1  口径矩阵"),
    (2, "4.2  为什么是 500 米与 30 分钟"),
    (2, "4.3  “到过”与“停留”差 1,244 人"),
    (1, "5  停留识别：把信令压成停留"),
    (2, "5.1  人没动，基站在变"),
    (2, "5.2  算法与结果"),
    (2, "5.3  参数敏感性"),
    (1, "6  几点来：傍晚的陡坡"),
    (2, "6.1  在场人数与首次出现"),
    (2, "6.2  17 点前后的跳变"),
    (2, "6.3  观测边界"),
    (1, "7  待多久：右删失下的“至少”"),
    (1, "8  从哪来：过夜地与距离"),
    (1, "9  是谁：四类客群"),
    (2, "9.1  分类规则"),
    (2, "9.2  四类人的画像"),
    (2, "9.3  周边居民的“停留”不是到访"),
    (1, "10  口径修正：外地来客从 1% 到 14%"),
    (2, "10.1  反常的数字"),
    (2, "10.2  被漏掉的是入城轨迹"),
    (2, "10.3  修正结果与下限"),
    (1, "11  还去了哪：三商圈联动"),
    (1, "12  一条能每天跑的流水线"),
    (1, "13  结论与建议"),
    (1, "14  使用边界：能说的话与不能说的话"),
    (2, "14.1  可以直接引用的三句话"),
    (1, "附录 A  指标口径与证据索引"),
    (1, "附录 B  图表与数据资产清单"),
]
for lv, text in TOC:
    toc_entry(text, page_of(text), lv)

doc.add_paragraph()

# ── 管理摘要 ────────────────────────────────────────────────────────────
page_break()
h1("管理摘要")
lead_p(
    "分析结论为口径内可用  这些数字回答的是“这批人”在西塔的行为，不是西塔的客流。"
)
body_p(
    f"样本是 2018 年 10 月 3 日全天的移动信令，清洗后 {n(N_DWD)} 条记录、{n(N_USERS)} 个完整用户标识。"
    f"把这批人的信令切成 144,239 个位置段，其中持续 30 分钟以上的 19,015 段被认定为停留；"
    f"{pc(N_STAY_USER / N_USERS)} 的用户至少有一个停留，人均 {N_STAY / N_USERS:.2f} 个。"
)
body_p(
    f"在西塔 500 米内停留不少于 30 分钟的有 {n(N_XITA)} 人；其中这次停留结束时刻不早于 17:00 的 "
    f"{n(N_VISITOR)} 人，是本报告定义的傍晚访客，占样本用户的 {pc(N_VISITOR / N_USERS)}。"
    "到场是陡的：17 点西塔在场人数从 16 点的 459 人跳到 1,254 人；17—19 点首次出现 1,978 人，"
    f"占“到过西塔”的 {n(N_ANY500)} 人的 40.81%。"
)

table(
    "关键分析结果",
    ["关键指标", "本次分析结果", "口径与管理含义"],
    [
        ["傍晚访客", "3,310 人", "停留结束不早于 17:00，占样本用户 58.65%"],
        ["西塔停留", "3,603 人 / 19,015 个", "质心距热点 ≤ 500 米、持续 ≥ 30 分钟"],
        ["停留时长", "中位至少 2.7 小时", "41% 到 23 点仍在；数据 23:59 截止"],
        ["能识别过夜地", "3,607 人（63.91%）", "与 0—6 点重叠最长且 ≥ 60 分钟"],
        ["客群构成", "市内 38.70% 周边 22.63% 外地 14.29% 不明 24.38%", "过夜地 + 当日入城轨迹"],
        ["商圈联动", "太原街 15.0% / 中街 11.2%", "到达西塔前的 ≥ 30 分钟停留"],
    ],
    [3.4, 5.0, 7.6],
    first_left=True,
)

body_p(
    "傍晚访客在西塔的停留中位数至少 2.7 小时，41% 的人到 23 点仍在西塔。数据在 23:59 截止，"
    "因此这个时长是下限；越晚到的人越可能跨过 23 点，22 点到的访客中 97.79% 如此。"
)
body_p(
    "按过夜地与当日入城轨迹划分，傍晚访客中市内来访占 38.70%、周边居民 22.63%、外地来客 14.29%，"
    "另有 24.38% 识别不出过夜地。到西塔之前有 15.0% 在太原街停留过，离开太原街后中位 70 分钟到西塔；"
    "中街更低（11.2%）也更远（134 分钟）。"
)
body_p(
    "需要先说清一件事：换一套半径与最短时长，“到访人数”会在 1,836 到 5,282 人之间，相差 2.9 倍。"
    "本报告统一采用 500 米 / 30 分钟口径，并在第 4 章列出全部 12 种结果——引用本报告数字的地方，"
    "都应同时带上这两个参数。"
)
body_p(
    "三章的读法：第 1—5 章定口径，说明每个数字是怎么算出来的；第 6—11 章回答业务问题，"
    "每章一个问句；第 12—14 章交代工程可复现性与使用边界。所有图都带“口径与来源”一行，"
    "表都带口径列，目的是让读者能自己复核，而不是相信。"
)

# ── 1 ──────────────────────────────────────────────────────────────────
h1("1  分析问题与口径")
body_p(
    "甲方原话是：“国庆期间我们想了解一下区里的夜间经济情况，你们运营商有数据，帮我们看看。”"
    "这句话里没有一个字段可以直接查询：哪一天、哪一级行政区、什么叫夜间、看人数还是看消费，"
    "都得先定下来，否则任何数字都能被解释成对的。"
)
body_p(
    "数据本身的圈选范围给出了答案。样本用户在 10 月 3 日有 97.32% 到过和平区、85.88% 到过西塔 500 米范围"
    "（第 2、3 章），它不是全市随机抽样，而是“当天到过西塔一带的人”的完整轨迹。"
    "于是问题改写成四个可以计算的问句：几点来、待多久、从哪来、还去了哪。"
)
table(
    "需求改写：能回答与不能回答",
    ["业务问题", "能否回答", "口径或原因"],
    [
        ["这次傍晚来了多少人", "能", "3,310 人（500 米内、停留 ≥ 30 分钟、17:00 后仍在）"],
        ["几点来", "能", "逐小时在场人数与首次出现人数，17—19 点是峰值"],
        ["待多久", "能，但是下限", "中位至少 2.7 小时；41% 到 23 点仍在，数据 23:59 截止"],
        ["从哪来", "能到区县与距离", "过夜地区县 + 直线距离；不区分交通方式"],
        ["还去了哪", "能，限三个商圈", "到达前的停留地点；先后顺序不代表因果"],
        ["全市夜间人流", "不能", "样本按“到过西塔”圈选，不能外推全市"],
        ["工作日与节假日对比", "不能", "只有 10 月 3 日一天有效样本"],
        ["总人数（含联通、电信）", "不能", "全部为移动用户，缺市场份额扩样参数"],
    ],
    [4.4, 3.2, 8.4],
    first_left=True,
)
body_p(
    "表 2 最后三行不是数据没做好，而是数据本身回答不了。报告里凡是涉及这三类的表述一律改写或删除——"
    "给出一个看起来合理的数字，比承认不知道更危险。"
)
body_p(
    "能回答的部分，结论依赖三组口径：热点中心落在哪、多大的圈算“在西塔”、多长的停留算“来过”。"
    "这三件事一旦确定，后面所有数字都是确定的；一旦改动，所有数字一起变。表 3 是它们的取值与依据。"
)
table(
    "分析口径与参数",
    ["口径项", "取值", "是否敏感", "依据与落地位置"],
    [
        ["热点中心", "123.410582, 41.806944", "否", "前 5 个站点按连接用户数加权（dim_hotspot）"],
        ["热点半径", "500 米", "是", "300—5000 米覆盖 72.08%—99.66% 用户"],
        ["切段半径", "500 米", "否", "200—1000 米人均停留点只差 0.18 个"],
        ["最短停留", "30 分钟", "是", "5—60 分钟人均停留点从 6.24 降到 2.38 个"],
        ["傍晚阈值", "17:00", "否", "西塔停留的结束时刻不早于 17:00"],
        ["过夜时段", "0:00—6:00", "否", "与此时段重叠最长的停留即为过夜地"],
        ["过夜最小重叠", "60 分钟", "否", "重叠不足 60 分钟的不计为过夜地"],
        ["周边居民", "过夜地距 1.5 公里内", "否", "用于第 9 章分群"],
        ["每小时定位", "覆盖 ≥ 30 分钟", "否", "不足时改用该小时信令位置的中位数"],
        ["对外披露", "少于 5 人不展示", "—", "交付口径，见配置 privacy.min_cell_users"],
    ],
    [3.0, 4.2, 2.2, 6.6],
    first_left=True,
)
body_p(
    "“是否敏感”一列来自第 5 章的敏感性分析：不敏感的参数用行业常用值即可，敏感的参数必须写进每一张图的口径行。"
    "这也是本报告所有图都带“口径与来源”、所有表都带口径列的原因。"
)

# ── 2 ──────────────────────────────────────────────────────────────────
h1("2  数据与样本")
body_p(
    f"原始接入 {n(N_ODS)} 条记录，按关键字段缺失、标识格式异常、完全重复、日期筛选四步清洗后留下 "
    f"{n(N_DWD)} 条。四步合计剔除 {n(N_ODS - N_DWD)} 条，其中 84.61% 是“不是 10 月 3 日”——"
    "这一项属于分析范围筛选，不是脏数据；质量清洗本身只剔除了 2,600 条（0.4880%）。"
    "清洗过程的逐项对账见《数据质量分析报告》，本报告不重复。"
)
figure(
    "D01_01_各日记录分布.png",
    "三日记录的 97.30% 集中在 10 月 3 日",
    "ODS 原始记录 532,828 条；按 timestamp 所属日期计数；三日的用户标识会重复出现，不可相加。",
)
table(
    "各日原始接入记录与出现用户",
    ["日期", "记录数", "记录占比", "出现用户数"],
    [
        [
            f"{int(str(r['日期']).split('-')[0])} 月 {int(str(r['日期']).split('-')[1])} 日",
            n(int(r["记录数"])),
            pc(r["记录占比"]),
            n(int(r["用户数"])),
        ]
        for _, r in DAILY.iterrows()
    ],
    [4.0, 4.0, 4.0, 4.0],
)
body_p(
    "10 月 1 日只有 54 条、53 个用户，10 月 2 日 14,331 条。样本的采集窗口是逐步建立的，"
    "10 月 3 日才是第一天完整数据。所以本报告只做单日分析，不做三日趋势、同比或环比；"
    "要做节假日对比，得先补齐采集规则相同的连续日期。"
)
body_p(
    f"表 4 数的是原始接入（ODS）；清洗到明细层后，10 月 3 日剩 {n(N_DWD)} 条记录、{n(N_USERS)} 个用户"
    "（表 4 的 5,652 人里含标识格式异常与重复记录）。"
    f"这 {n(N_DWD)} 条记录平均每人 91.4 条；识别出 19,015 个停留与 144,239 个位置段；"
    f"逐小时定位表 dws_user_hour 共 {n(N_HOUR)} 个人—小时，"
    f"平均每人每天 {N_HOUR / N_USERS:.1f} 个小时可定位。"
)
body_p(
    "这个“18 个小时”是后面所有时长结论的前提：信令只记录有事件的时刻，人待在原地也可能几个小时没有一条记录。"
    "停留识别之所以必须按时间切段而不是按信令条数统计，原因就在这里。"
)
figure(
    "D4_01_各区到访用户占比.png",
    "和平区覆盖 97.32%，康平县只有 0.32%",
    "dwd_signal 日活用户 5,644 人；“到访”指当天在该区县基站上至少出现过一条记录。",
)
table(
    "区县到访覆盖",
    ["区县", "到访用户占比", "折合人数"],
    [[r["district"], pc(r["到访用户占比"]), n(round(r["到访用户占比"] * N_USERS))] for _, r in REACH.iterrows()],
    [4.0, 6.0, 6.0],
    first_left=True,
)
body_p(
    "和平区 97.32%、沈河区 56.91%、皇姑区 54.45%、铁西区 51.54%，而康平 0.32%、法库 0.83%，"
    "最高与最低相差 305 倍。这不是沈阳的人口分布，而是圈选方式留下的指纹：样本是“当天到过西塔一带”的人，"
    "他们的活动必然集中在和平区及相邻城区。"
)
body_p(
    "由此得到两条限制。第一，样本内人数不能当作西塔的实际客流——它只是“中国移动用户、且当天到过西塔”的那部分。"
    "第二，任何“沈阳人如何如何”的说法都不成立，因为样本对城市西部与北部的覆盖几乎是空的。"
)

# ── 3 ──────────────────────────────────────────────────────────────────
h1("3  空间口径：热点、半径与商圈")
body_p(
    "西塔是一个商圈名，不是一个坐标。项目没有手工点一个位置，而是取当天连接用户数最多的 5 个站点，"
    "按各自用户数加权求重心，得到 123.410582、41.806944。"
)
body_p(
    "手工点坐标的问题是无法复核：换一个人、换一天，点会落在不同路口，之后所有半径与距离都跟着漂。"
    "用数据定中心，换谁都能用同一条查询复现；这也是第 12 章流水线能把热点作为一步自动生成的原因。"
)
figure(
    "D4_02_西塔热点.png",
    "西塔热点由前 5 个站点加权确定，500 米范围覆盖韩百商场一带",
    "dim_hotspot 一行记录；5 个站点为当日连接用户数前 5，权重为各自连接用户数。",
)
body_p(
    f"从中心往外放半径，到过的用户占比依次为 72.08%、85.88%、93.59%、97.80%、99.66%。"
    "500 米到 1000 米只增加 7.71 个百分点，再往外 4 公里只增加 6.07 个百分点——"
    "半径超过 1 公里后，“在西塔”这个说法就不再有区分度。"
)
table(
    "热点半径覆盖",
    ["半径", "到过用户占比", "折合人数"],
    [[f"{int(r['r'])} 米", pc(r["p"]), n(round(r["p"] * N_USERS))] for _, r in HOT_R.iterrows()],
    [4.0, 6.0, 6.0],
)
body_p(
    "“到过”与“停留”是两回事：500 米内只要有一条信令就算到过（4,847 人），"
    "而有 30 分钟以上停留的只有 3,603 人。第 4 章会把这两个口径摆在一起，说明差的 1,244 人是谁。"
)
xh_morning = XITA_H.loc[9:16, "在场人数"]
body_p(
    f"把“人在哪”按小时固化，就得到三个商圈的一天。西塔在 0 点就有 {n(int(XITA_H.loc[0, '在场人数']))} 人在场，"
    f"上午 9—16 点稳定在 {n(int(xh_morning.min()))}—{n(int(xh_morning.max()))} 人，"
    f"17 点跳到 {n(int(XITA_H.loc[17, '在场人数']))} 人，20 点达到 {n(int(XITA_H['在场人数'].max()))} 人。"
    "太原街与中街的曲线完全不同："
    f"中街在 11—16 点爬升到 {n(int(ZONE[ZONE['小时'].between(11, 16)]['中街商圈'].max()))} 人的峰值，晚上反而回落；"
    f"太原街则从 300 人左右缓慢上行，21 点仍有 {n(int(ZONE.set_index('小时').loc[21, '太原街商圈']))} 人。"
)
zone_rows = []
for lo in range(0, 24, 3):
    part = ZONE[(ZONE["小时"] >= lo) & (ZONE["小时"] < lo + 3)]
    xh = XITA_H[(XITA_H.index >= lo) & (XITA_H.index < lo + 3)]["在场人数"]
    label = f"{lo:02d}—{lo + 3:02d} 时" if lo + 3 <= 23 else f"{lo:02d}—23 时"
    zone_rows.append(
        [
            label,
            n(int(part["可定位人数"].mean())),
            n(int(xh.mean())),
            n(int(part["太原街商圈"].mean())),
            n(int(part["中街商圈"].mean())),
        ]
    )
table(
    "三商圈分时段平均在场人数",
    ["时段", "可定位人数", "西塔", "太原街商圈", "中街商圈"],
    zone_rows,
    [3.2, 3.4, 3.0, 3.4, 3.0],
    first_left=True,
)
body_p(
    "“可定位人数”是分母：19 点 5,069 人可定位，占样本的 89.81%，即每 10 个人里有 1 个在这个时刻既没有停留覆盖、"
    "也没有信令。所有人时占比都用当小时的可定位人数作分母，不用 5,644，否则夜间会系统性低估。"
)

# ── 4 ──────────────────────────────────────────────────────────────────
h1("4  到访人数：一个数字，十二种口径")
body_p(
    "同一个“来了多少人”，在 3 个半径 × 4 种时长口径下有 12 个答案，从 1,836 到 5,282 人，相差 2.9 倍。"
    "这不是数据有错，而是问题没问完：半径决定“哪里算西塔”，最短时长决定“什么算来过”。"
)
cal_rows = []
for r_ in ("300米", "500米", "1000米"):
    part = CALIBER[CALIBER["半径"] == r_].set_index("口径")
    cal_rows.append(
        [
            r_,
            n(int(part.loc["任意一条信令", "人数"])),
            n(int(part.loc["停留>=30分钟", "人数"])),
            n(int(part.loc["停留>=60分钟", "人数"])),
            n(int(part.loc["停留>=120分钟", "人数"])),
        ]
    )
h2("4.1  口径矩阵")
table(
    "12 种口径下的西塔到访人数",
    ["半径", "任意一条信令", "停留 ≥ 30 分钟", "停留 ≥ 60 分钟", "停留 ≥ 120 分钟"],
    cal_rows,
    [2.6, 3.4, 3.4, 3.4, 3.4],
)
figure(
    "D7_01_到访人数口径对比.png",
    "同一批人、12 种口径，到访人数相差 2.9 倍",
    "ads_caliber_visitors；半径为以热点为中心的圆，最短时长为当次停留的持续时长。",
)
body_p(
    "最宽的口径（1000 米、任意一条信令）5,282 人，等于“今天在 1 公里内冒出过一次”；"
    "最严的口径（300 米、≥ 120 分钟）1,836 人，等于“在塔附近待满两小时”。"
    "前者会把穿行、换乘的人算进来，后者会把吃顿饭就走的客人删掉。两者都能叫“到访”，但说的是不同的事。"
)
h2("4.2  为什么是 500 米与 30 分钟")
body_p(
    "本报告采用 500 米 / 30 分钟，得 3,603 人。理由有三条：500 米与商圈实际边界的贴合度可在图 3 上直接检验；"
    "300 米到 1000 米之间的差异来自边缘街区而非核心区；30 分钟是商业分析里区分“路过”与“到访”的常用门槛，"
    "而且它在第 5 章的敏感性里是影响最大的参数，必须显式声明。"
)
h2("4.3  “到过”与“停留”差 1,244 人")
body_p(
    f"“到过”4,847 人与“停留”3,603 人差 1,244 人，占 25.67%。这 1,244 人在 500 米内有过信令，"
    "但没有停留够 30 分钟——他们可能是穿行、换乘，或者只是在附近短暂停留。"
    "本报告凡写“到访人数”，一律指后者；写“到过”时才用前者。"
)

# ── 5 ──────────────────────────────────────────────────────────────────
h1("5  停留识别：把信令压成停留")
h2("5.1  人没动，基站在变")
body_p(
    "手机在楼里不动，连接的基站也会在几个扇区之间来回跳。以相邻两条记录是否更换站点计，45% 的相邻记录换了站；"
    "换站时两站距离的中位数是 666.1 米，62.4% 在一公里以内；10 分钟内又切回原站点的 A→B→A 占全部切换的 6.7%。"
)
body_p(
    "如果直接用“当前基站坐标”代表位置，一个人在原地待两小时，轨迹会出现几十次一两公里的来回。"
    "停留识别的半径参数，首先是为了吸收这类抖动，而不是为了定义商圈。"
)
figure(
    "D6_02_站点切换距离.png",
    "换站距离中位 666 米，六成在一公里以内",
    "515,923 条带坐标记录；按用户与时间排序后比较相邻记录；A→B→A 要求 10 分钟内返回。",
)
h2("5.2  算法与结果")
body_p(
    "算法是顺序扫描：每个人的信令按时间排序，第一条开一个段并记下段的质心；下一条离质心不超过 500 米就并入、"
    "更新质心，超过就结束当前段并另开一段。扫描结束后，持续不少于 30 分钟的段叫停留，其余是经过。"
    "半径 R 用来吸收乒乓切换，时长 T 用来区分“停下来过”和“路过”。"
)
table(
    "停留识别结果",
    ["指标", "结果", "说明"],
    [
        ["带坐标信令", "515,923 条", "ODS 去重与日期筛选后，空间关联成功的记录"],
        ["位置段", "144,239 个", "按 500 米半径切段，人均 25.6 段"],
        ["停留（≥ 30 分钟）", "19,015 个", "占全部位置段的 13.18%"],
        ["有停留的用户", f"5,506 人  {pc(N_STAY_USER / N_USERS)}", "其余 138 人当天没有 30 分钟以上的停留"],
        ["人均停留", f"{N_STAY / N_USERS:.2f} 个", "分母为全部 5,644 个用户"],
        ["计算耗时", "1.2 秒", "纯 Python 单线程，含质心更新"],
    ],
    [4.0, 5.0, 7.0],
    first_left=True,
)
figure(
    "D6_01_一个人的一天.png",
    "一个典型用户的一天：凌晨在 17.7 公里外，17:12 进入西塔 500 米内",
    "示例用户当日 96 条信令；横轴为时刻，纵轴为距西塔中心的直线距离；色带为 500 米范围。",
)
body_p(
    "51 万条信令被压成 19,015 个停留，压缩比约 27:1。之后所有“在哪、待多久”的分析都在这张停留表上做，"
    "不再碰原始信令；这也是 D6 之后流水线能在 10 秒内跑完的原因。"
)
h2("5.3  参数敏感性")
table(
    "停留参数敏感性：人均停留点个数",
    ["半径（米）", "≥ 5 分钟", "≥ 15 分钟", "≥ 30 分钟", "≥ 45 分钟", "≥ 60 分钟"],
    [
        [
            f"{int(radius)}",
            *[
                f"{SENS[(SENS['半径(米)'] == radius) & (SENS['最短时长(分)'] == t)]['人均停留点'].iloc[0]:.2f}"
                for t in (5, 15, 30, 45, 60)
            ],
        ]
        for radius in (200, 300, 500, 800, 1000)
    ],
    [2.8, 3.3, 3.3, 3.3, 3.3, 3.3],
)
figure(
    "D06_04_停留参数敏感性.png",
    "半径不敏感、时长敏感：参数影响的方向决定口径怎么写",
    "ads_stay_sensitivity 共 25 组参数；纵轴为人均停留点个数，分母为 5,644 个用户。",
)
body_p(
    "半径从 200 米放大到 1000 米，人均停留点只从 3.36 个变到 3.18 个，差 0.18 个——结果对半径不敏感，"
    "用行业常用的 500 米即可。最短时长从 5 分钟拉到 60 分钟，人均停留点从 6.24 个降到 2.38 个，差 2.6 倍——"
    "结果对时长敏感，所以“至少 30 分钟”必须写进每一处口径说明。"
)
body_p(
    "敏感性分析在这里的作用不是“证明 500/30 是唯一正确的”，而是告诉读者两件事：换一个半径，结论基本不变；"
    "换一个时长，人数会差一倍以上。前者可以省略说明，后者不能。"
)

# ── 6 ──────────────────────────────────────────────────────────────────
h1("6  几点来：傍晚的陡坡")
XH = XITA_H["在场人数"]
h2("6.1  在场人数与首次出现")
body_p(
    f"把 24 小时摊开看，西塔的在场人数不是缓慢爬升，而是在 17 点拐了一个弯：16 点 {n(int(XH.loc[16]))} 人、"
    f"17 点 {n(int(XH.loc[17]))} 人、18 点 {n(int(XH.loc[18]))} 人、19 点 {n(int(XH.loc[19]))} 人、"
    f"20 点达到峰值 {n(int(XH.max()))} 人；之后每小时减少 150—300 人，23 点仍有 {n(int(XH.loc[23]))} 人。"
)
h2("6.2  17 点前后的跳变")
body_p(
    f"17 点到 18 点之间增加 {n(int(XH.loc[18] - XH.loc[17]))} 人，是全天最大的一小时增量；"
    "0 点到 16 点所有小时的增量加起来，也不到这一个小时。这个结构说明西塔的客流不是“逐渐热起来”，"
    "而是被一个时点集中推上去的。"
)
figure(
    "D4_04_西塔在场与首次出现.png",
    f"17 点起在场人数翻倍，20 点达到峰值 {n(int(XH.max()))} 人",
    "ads_xita_hourly；在场 = 该小时有至少一条信令落在西塔 500 米内；柱为首次出现人数。",
)
body_p(
    "“首次出现”指这个人当天第一次在西塔 500 米内被观测到。17—19 点合计 1,978 人，"
    "占“到过西塔”的 4,847 人的 40.81%；其中 17 点一小时 708 人，是 16 点 50 人的 14.16 倍。"
)
table(
    "逐小时在场与首次出现",
    ["小时", "在场人数", "首次出现人数", "首次出现占比"],
    [
        [
            f"{int(h)}:00",
            n(int(XITA_H.loc[h, "在场人数"])),
            n(int(XITA_H.loc[h, "首次出现人数"])),
            f"{XITA_H.loc[h, '首次出现占比'] * 100:.2f}%",
        ]
        for h in range(16, 24)
    ],
    [3.0, 4.0, 4.2, 4.2],
    first_left=True,
)
body_p(
    "17 点前后的跳变是本报告最稳的一条结论：无论用在场人数（2.73 倍）、首次出现（14.16 倍），"
    "还是 12 种口径中的任何一种，陡坡都出现在 17 点。它对应的是下班与晚饭时间，而不是夜生活——"
    "后者要到 20—21 点才完整。"
)
h2("6.3  观测边界")
body_p(
    "两个观测边界。第一，样本第一天从 0 点开始，“首次出现”最早只能追到 0 点，所以 0 点那部分人里"
    "有一部分其实更早就到了，17—19 点的 40.81% 因此是下限。第二，数据在 23:59 截止，23 点之后发生什么，"
    "数据里没有；第 7 章会把这件事单独讲清楚。"
)

# ── 7 ──────────────────────────────────────────────────────────────────
h1("7  待多久：右删失下的“至少”")
body_p(
    "3,310 个傍晚访客在西塔的停留中位数是 2.7 小时。注意它是“把一个人当天所有西塔停留加总”后的中位数——"
    "同一个人可能傍晚来、22 点出去吃宵夜、23 点再回来，报告算的是他在西塔累计待了多久，不是一次连续到访。"
)
body_p(
    "这个数字有三个口径成分：只算 500 米内的停留、只算 30 分钟以上的停留、只算结束时刻不早于 17:00 的那次停留。"
    "换掉任何一条，2.7 小时就不成立。"
)
table(
    "到达时刻与跨过 23 点的比例",
    ["首次到达小时", "23 点后仍在西塔", "读法"],
    [
        [
            f"{int(r['首次到达小时'])}:00",
            f"{r['23点后扔在的占比'] * 100:.2f}%",
            {
                17: "刚下班就来，多半会回家",
                18: "与 17 点接近，仍是当日往返",
                19: "开始出现跨夜的苗头",
                20: "一半以上会跨过 23 点",
                21: "绝大多数会跨夜",
                22: "几乎必然跨夜",
            }.get(int(r["首次到达小时"]), "—"),
        ]
        for _, r in CENSOR.iterrows()
    ],
    [4.0, 5.0, 7.0],
    first_left=True,
)
figure(
    "D7_03_停留时长删失.png",
    "22 点到西塔的访客，97.79% 会跨过 23 点",
    "ads_xita_censoring；分母为该小时到达的傍晚访客；数据在 23:59 截止，无法观测到之后。",
)
body_p(
    "越晚到，越可能跨过 23 点：17 点到的只有 9.60% 在 23 点后仍留在西塔，19 点 20.88%，20 点 55.32%，"
    "21 点 86.67%，22 点 97.79%。整体 41% 的访客到 23 点仍在。"
)
body_p(
    "但数据在 23:59 截止，23 点后仍在西塔的人，其停留时长只能算到 23:59，真实时长可能更长。"
    "所以本报告一律写“至少 2.7 小时”，不写“平均停留 2.7 小时”——前者是数据能证明的，后者不是。"
)
body_p(
    "要得到真实时长，需要跨日数据：把 10 月 4 日 0—6 点的信令接上，看这批人什么时候真正离开西塔。"
    "这是本报告提出的第一条数据需求，也是“夜间经济”这个问题里最需要补的一块。"
)

# ── 8 ──────────────────────────────────────────────────────────────────
h1("8  从哪来：过夜地与距离")
body_p(
    f"只有 63.91%（{n(N_NIGHT)}/{n(N_USERS)}）的用户能识别出过夜地。原因是圈选：样本只包含“10 月 3 日到过西塔”的人，"
    "如果他当天凌晨还在外地、白天才进城，凌晨那段信令根本不在样本里，于是识别不出过夜地。"
)
body_p(
    "识别规则是：与 0—6 点重叠时间最长、且重叠不少于 60 分钟的停留，取它的位置作为过夜地。"
    "它不等于“家”，只是“当天凌晨待得最久的地方”——上夜班的人、住酒店的人、通宵在路上的人，都会被算成他们当时所在的位置。"
)
body_p(
    f"能识别过夜地的 {n(N_NIGHT)} 人里，33.10% 的过夜地在西塔 1.5 公里内，34.74% 在 1.5—5 公里，"
    "26.50% 在 5—15 公里，5.66% 在 15 公里以外；中位距离 2.9 公里。"
)
table(
    "过夜地到西塔的直线距离",
    ["距离档", "占比", "折合人数"],
    [[r["band"], pc(r["p"]), n(round(r["p"] * N_NIGHT))] for _, r in NIGHT_D.iterrows()],
    [5.0, 5.0, 5.0],
    first_left=True,
)
figure(
    "D7_04_过夜地距离.png",
    "一半的过夜地离西塔不到 2.9 公里",
    "dws_night 共 3,607 人；距离为过夜地质心到热点中心的直线距离，非路网距离。",
)
_ND = NIGHT_DIST.set_index("night_district")["n"]


def _nd(key):
    return pc(float(_ND.get(key, 0)) / N_NIGHT)


body_p(
    f"按区县看，和平区 {_nd('和平区')}，铁西区 {_nd('铁西区')}、皇姑区 {_nd('皇姑区')}，"
    f"沈河区 {_nd('沈河区')}，于洪区 {_nd('于洪区')}，大东区 {_nd('大东区')}，"
    f"浑南区 {_nd('浑南区')}，市外 {_nd('市外')}。西塔访客的主体是本市居民，"
    "外地客在修正口径之前只有 1%（第 10 章）。"
)
night_rows = [
    [("（未识别）" if pd.isna(r["night_district"]) else r["night_district"]), n(int(r["n"])), pc(r["n"] / N_NIGHT)]
    for _, r in NIGHT_DIST.iterrows()
]
table(
    "过夜地区县分布",
    ["区县", "人数", "占比"],
    night_rows,
    [5.0, 5.0, 5.0],
    first_left=True,
)
figure(
    "D7_05_过夜地分布.png",
    "过夜地集中在西塔周边，和平区占 37.9%",
    "dws_night；区县由过夜地质心与行政区边界匹配；市外 = 落在沈阳市域外。",
)

# ── 9 ──────────────────────────────────────────────────────────────────
h1("9  是谁：四类客群")
h2("9.1  分类规则")
body_p(
    "分群用规则而不是聚类，因为规则能解释、能复核、能交给甲方自己算。第一版只用一条证据——过夜地在哪，"
    "按顺序判四类：先判“过夜地不明”（0—6 点没有 ≥ 60 分钟的停留），再判“市外来访”（过夜地在沈阳市域外），"
    "再判“周边居民”（过夜地距西塔不足 1.5 公里），剩下的都是“市内来访”。"
)
table(
    "第一版四类客群：只按过夜地",
    ["客群", "判定条件", "人数", "占比", "停留中位（分）", "首次到达（时）"],
    [
        [
            r["客群"],
            {
                "市内来访": "有本市过夜地，且不在 1.5 公里内",
                "周边居民": "过夜地距西塔 < 1.5 公里",
                "市外来访": "过夜地在沈阳市域外",
                "过夜地不明": "0—6 点没有 ≥ 60 分钟的停留",
            }.get(r["客群"], "—"),
            n(int(r["人数"])),
            pc(r["人数"] / V1_TOTAL),
            f"{V1_MED[r['客群']][0]:.1f}",
            f"{V1_MED[r['客群']][1]:.2f}",
        ]
        for _, r in V1.iterrows()
    ],
    [3.0, 5.4, 2.2, 2.2, 2.4, 2.4],
    first_left=True,
)
figure(
    "D8_01_傍晚访客客群.png",
    "第一版里 39% 市内来访、38% 过夜地不明、1% 外地",
    "dws_visitor_tag.segment；占比分母为 3,310 名傍晚访客。",
)
body_p(
    "判断顺序很关键。如果先判“周边居民”，没有过夜地的人会因为缺失值（NaN）与 1.5 比较返回 False 而漏进“市内来访”，"
    "1,243 个“识别不出过夜地”的人就会被算成“本市人”。先判缺失值是 D08 里专门修过的一处口径。"
)
h2("9.2  四类人的画像")
body_p(
    "四类人的画像差别很大：市内来访中位 18.76 时到达、在西塔停留 144.1 分钟；市外来访 19.46 时到达、130.0 分钟；"
    "过夜地不明 18.75 时到达、139.4 分钟。三者行为几乎一致——都是“傍晚来、待两个多小时”的访客。"
)
figure(
    "D07_01_西塔客群画像.png",
    "四类客群：几点到、待多久（第一版）",
    "dws_visitor 共 3,310 人；中位数为各组中位数，不按人数加权。",
)
h2("9.3  周边居民的“停留”不是到访")
body_p(
    "周边居民是例外：他们在西塔的停留中位 620.4 分钟（10.3 小时），首次出现在 1.00 时。这不是到访，而是居住——"
    "他们整天就在这一带，停留识别把居家时间也算成了“在西塔的停留”。"
)
body_p(
    "所以停留时长只能在三类“访客”之间比较。把周边居民的 10.3 小时和市内来访的 2.4 小时放在一起说“平均停留”，"
    "会同时高估访客、误读居民。这也解释了第 7 章那个 2.7 小时为什么比三类的 2.2—2.4 小时都高：它把居民的长停留也平均了进去。"
)
note(
    "第一版还有一个明显不对的地方：国庆假期、核心商圈，外地人只占 0.94%。第 10 章查这一条。"
)

# ── 10 ─────────────────────────────────────────────────────────────────
h1("10  口径修正：外地来客从 1% 到 14%")
h2("10.1  反常的数字")
body_p(
    "第一次按过夜地分群，外地来客只有 31 人、占 0.94%。国庆假期、核心商圈、全市最大的人口流入时段，"
    "外地人只占 1%——这个数字不合常理，第一反应应该是口径错了，而不是把它抄进报告。"
)
h2("10.2  被漏掉的是入城轨迹")
body_p(
    "追查下来，问题出在“只有过夜地一条证据”。当天白天才从外地进城的人，凌晨还在外地，信令不在样本里，"
    "过夜地识别不出来，于是被归进“过夜地不明”。不明的那一类因此显得特别大（1,243 人，37.55%）。"
)
body_p(
    "修正的办法是加一条独立证据：一个人当天第一条信令在市域外、之后进入市域，就是外地来客——不管他有没有过夜地。"
    "过夜地说“昨晚睡在哪”，入城轨迹说“今天从哪来”，两条证据合起来，才覆盖得住国庆这种当天往返的出行。"
)
h2("10.3  修正结果与下限")
figure(
    "D8_02_外地来客口径修正.png",
    "加一条入城轨迹，外地来客从 31 人变成 473 人",
    "dws_visitor_tag.segment_v2；入城 = 首条信令落在市外且其后出现市域内记录；分母 3,310 人。",
)
table(
    "修正前后四类客群对比",
    ["客群", "第一版（只按过夜地）", "修正后（加当日入城）", "变化"],
    [
        ["市内来访", "1,286", n(int(SEG[SEG["客群"] == "市内来访"]["人数"].iloc[0])), "−5"],
        ["过夜地不明", "1,243", n(int(SEG[SEG["客群"] == "过夜地不明"]["人数"].iloc[0])), "−436"],
        ["周边居民", "750", n(int(SEG[SEG["客群"] == "周边居民"]["人数"].iloc[0])), "−1"],
        ["外地来客", "31", n(int(SEG[SEG["客群"] == "外地来客"]["人数"].iloc[0])), "+442"],
    ],
    [4.0, 4.6, 4.6, 2.8],
    first_left=True,
)
body_p(
    "修正后外地来客 473 人（14.29%），其中 436 人原来被归为“过夜地不明”；“过夜地不明”从 1,243 人降到 807 人。"
    "这仍然是下限：0 点前就已进城、或者当天没在市域外留下第一条信令的人，这条证据同样抓不到。"
)
body_p(
    "这个修正没有让数字“变好看”，反而把原来 37.55% 的“不明”降到 24.38%。它值得写进报告，是因为它示范了一条原则："
    "反常的数字先查口径，再决定要不要用；改口径必须留下修正前后的两套结果，让人能看出差在哪。"
)

# ── 11 ─────────────────────────────────────────────────────────────────
h1("11  还去了哪：三商圈联动")
body_p(
    "对每个傍晚访客，取他在西塔那次“结束时刻不早于 17:00”的停留开始时刻，记为到达。“之前”是在到达前就已结束的、"
    "西塔以外的停留；“之后”是到达之后才开始的停留。每个停留按位置归入过夜地（离过夜地 500 米内）、太原街商圈、"
    "中街商圈或其他地点。"
)
body_p(
    "一个人可以同时属于几类，所以各行占比加起来超过 100%，不能相加，也不能画成饼图或桑基图——"
    "“去了太原街”和“去了中街”不是互斥事件，同一个人一天里可能两边都去。"
)
table(
    "到达西塔前后的商圈停留",
    ["地点", "之前人数", "之前占比", "之后人数", "之后占比"],
    [
        [
            r["地点"],
            n(int(r["之前人数"])),
            pc(r["之前占比"]),
            n(int(r["之后人数"])),
            pc(r["之后占比"]),
        ]
        for _, r in LINK.iterrows()
    ],
    [3.6, 3.2, 3.2, 3.2, 3.2],
    first_left=True,
)
figure(
    "D8_03_商圈联动.png",
    "太原街是西塔最主要的上游商圈，中街弱得多",
    "ads_xita_linkage；分母 3,310 名傍晚访客；一人可属多类，各行占比不可相加。",
)
body_p(
    "15.0%（498 人）的傍晚访客到西塔之前在太原街停留过，离开太原街后中位 70 分钟到西塔；中街是 11.2%（370 人）、134 分钟。"
    "离开西塔之后再去太原街的只有 7.0%（231 人），去中街的 1.1%（35 人）。"
)
body_p(
    "两个方向合起来看：太原街→西塔 498 人、西塔→太原街 231 人，进多出少；中街→西塔 370 人、西塔→中街 35 人，"
    "几乎是单向的。这与地理一致：太原街与西塔同属和平区、步行可达；中街在沈河区，需要乘车，天然不构成步行联动。"
)
body_p(
    "三个限制。第一，先后顺序不是因果，数据只能说明“同一天里既去了 A 又去了 B”，不能说明是被 A 吸引来的。"
    "第二，只统计停留 ≥ 30 分钟的地点，路过不算。第三，没有消费数据，所谓“联动”只是人流联动，不是消费联动。"
)

# ── 12 ─────────────────────────────────────────────────────────────────
h1("12  一条能每天跑的流水线")
body_p(
    f"从 ODS 到停留识别一共 {len(ETL)} 步，一条命令跑完，总耗时约 {ETA_TOTAL:.1f} 秒（本地库、单机）。"
    "每一步的输入行数、输出行数和耗时都写进 etl_log，并带同一个批次号，任何时候都能回答“这张表是哪次跑出来的、当时有多少行”。"
)
def _v(x):
    return "—" if pd.isna(x) else n(int(x))


table(
    "流水线各步骤的输入输出与耗时",
    ["步骤", "输入行数", "输出行数", "耗时（秒）"],
    [
        [
            str(r["步骤"]),
            _v(r["输入行数"]),
            _v(r["输出行数"]),
            f"{r['耗时(秒)']:.2f}",
        ]
        for _, r in ETL.iterrows()
    ],
    [4.4, 4.0, 4.0, 3.6],
    first_left=True,
)
_top = ETL.dropna(subset=["耗时(秒)"]).sort_values("耗时(秒)", ascending=False).head(3)
slow = "、".join(f"{r['步骤']}（{r['耗时(秒)']:.2f} 秒）" for _, r in _top.iterrows())
body_p(
    f"最慢的三步依次是 {slow}。其中 build_stay 是唯一一步“算法型”的，"
    "其余都是 IO 或清洗；也就是说，这套流水线的瓶颈在数据库读写，不在计算。要提速先换库，不必优化算法。"
)
body_p(
    "同一天写两遍，dwd_signal 仍是 515,931 行；与 D02 手工清洗的结果逐列比对，不一致的列数为 0。"
    "时间字段以文本格式存储、毫秒位固定三位，避免了 pandas 读回时把毫秒抹掉、导致同一秒内多条记录排序错乱的问题。"
)
body_p(
    "半径、最短停留、傍晚阈值、过夜时段、周边居民距离、隐私下限都放在 configs/settings.yaml 里，"
    "代码里不出现 500 米、30 分钟这类业务数字。换参数只改一行配置，不改代码——这也是本报告能在第 4 章"
    "一次给出 12 种口径的原因。"
)
figure(
    "D5_03_数据质量检查汇总.png",
    "16 条稽核：通过 5 条、警告 6 条、不通过 5 条",
    "dq_check_result；按检查项计，不按严重度加权；逐条台账与处置见《数据质量分析报告》附录 A。",
)
body_p(
    "工程侧 78 项测试全部通过（1.11 秒），包括契约测试与单元测试；契约测试用真实库结构做对账，"
    "数据库结构一变，测试先红。数据侧 16 条稽核中 5 条不通过，全部是原始数据本身的问题（主键冲突、事件字典、商圈边界），"
    "已在《数据质量分析报告》中给出处置与残余限制。"
)
body_p(
    "把这两件事分开看很重要：测试保证“代码按约定运行”，稽核保证“数据按约定可信”。前者失败说明程序坏了，"
    "后者失败说明数据有洞；两者都通过，才谈得上“每天能跑、结果可追溯”。"
)

# ── 13 ─────────────────────────────────────────────────────────────────
h1("13  结论与建议")
body_p(
    "五条结论，每条都带口径。第一条：国庆傍晚的西塔是“陡坡型”客流，17 点起在场人数翻倍，20 点达峰 2,169 人，"
    "23 点仍有 1,820 人。"
)
body_p(
    "第二条：来的人以本市为主，市内来访 38.70%、周边居民 22.63%、外地来客 14.29%（修正后），另有 24.38% 识别不出过夜地。"
)
body_p(
    "第三条：停留至少 2.7 小时，41% 的人跨过 23 点；越晚到越可能过夜——22 点到的访客里 97.79% 会跨过 23 点，"
    "说明西塔的夜间消费时段集中在 21—23 点。"
)
body_p(
    "第四条：太原街是西塔最主要的上游商圈（15.0%、70 分钟），中街的联动弱一个量级（11.2%、134 分钟），"
    "且几乎是单向的。"
)
body_p(
    "第五条：所有数字都随口径变化，最宽与最窄相差 2.9 倍。本报告采用 500 米 / 30 分钟，任何引用都应带上这两个参数。"
)
body_p(
    "三条建议。第一，错峰引导：17—19 点 1,978 人集中到场，是全天最拥挤的时段；把一部分活动安排在 20 点后，"
    "既能分散入场压力，也贴合“越晚到越容易过夜”的行为。"
)
body_p(
    "第二，联动太原街：太原街→西塔 498 人、70 分钟可达，是现成的客流通道；两侧商户做联票、接驳或延时营业，"
    "比去中街拉客更划算。"
)
body_p(
    "第三，补夜间供给：41% 的访客 23 点后仍在西塔，23 点之后的服务（宵夜、打车、末班车衔接）是留客的关键；"
    "而这恰恰是需要跨日数据才能评估的部分。"
)
body_p(
    "三条限制。第一，只有 10 月 3 日一天有效样本，不能做趋势、同比或工作日对比。第二，全部为中国移动用户，"
    "缺少市场份额参数，无法换算为总客流。第三，样本是“当天到过西塔”的人，天然缺失“没来西塔的人”，"
    "因此不能算渗透率，也不能和全市人口对比。"
)

# ── 14 ─────────────────────────────────────────────────────────────────
h1("14  使用边界：能说的话与不能说的话")
body_p(
    "同一批数字，左列是数据能支撑的表述，右列是省掉限定后读起来更顺、但会被当成全市或全年结论的表述。"
    "对外发布时只用左列句式；要写右列，必须补上限定语或注明来源口径。"
)
table(
    "两种表述的对照",
    ["可以这样写", "不能这样写"],
    [
        ["17 点起西塔在场人数翻倍", "西塔每天 17 点开始上人"],
        ["样本内 3,310 人到访", "西塔国庆当天客流 3,310 人"],
        ["停留中位至少 2.7 小时", "客人平均停留 2.7 小时"],
        ["41% 的访客 23 点仍在西塔", "四成客人会过夜"],
        ["外地来客占 14.29%", "外地游客占一成五"],
        ["太原街是主要上游商圈", "太原街的客流都来了西塔"],
        ["17—19 点到场 1,978 人", "西塔傍晚每天来两千人"],
    ],
    [7.4, 7.4],
    first_left=True,
)
body_p(
    "这份报告能对外用的部分，是第 6—11 章的行为结构：陡坡、时长下限、商圈联动方向。这些结论在换样本、换日期后"
    "大概率仍然成立，因为它们描述的是行为模式，而不是某一天的具体人数。"
)
body_p(
    "不能对外用的，是任何被抽掉口径的绝对数。“3,310 人”“2.7 小时”“14.29%”只有在带上样本、单日、口径三个限定之后才成立；"
    "抽掉限定，它们就变成了另一种主张。"
)
h2("14.1  可以直接引用的三句话")
body_p(
    f"第一句：国庆当天傍晚，样本内 {n(N_VISITOR)} 人到过西塔，在西塔停留的中位时长至少 2.7 小时。"
    "这句话里的“样本内”“当天”“500 米 / 30 分钟”三个限定缺一不可。"
)
body_p(
    "第二句：17—19 点是入场高峰，17 点西塔在场人数是 16 点的 2.7 倍，20 点达到当天峰值 2,169 人。"
    "它描述的是行为节奏，换一天大概率仍然成立。"
)
body_p(
    "第三句：15.0% 的访客到西塔前在太原街停留，两处之间中位间隔 70 分钟——太原街是现成的上游客流。"
    "这句适合给招商和运营用，但不适合说成“太原街把客人送到了西塔”。"
)
note(
    "这三句可以直接抄进对外材料。替换其中任何一个数字时，要连同限定语一起换；"
    "只换数字不换限定，就变成了第 14 章开头右列那种表述。"
)

# ── 附录 A ─────────────────────────────────────────────────────────────
page_break()
h1("附录 A  指标口径与证据索引")
body_p("本表给出正文出现的主要指标的定义、口径与落地位置，供复核与二次引用。")
table(
    "",
    ["指标", "定义与口径", "落地表 / 字段", "章"],
    [
        ["记录保留率", "清洗后记录 ÷ 原始记录 = 515,931 ÷ 532,828", "dwd_signal / ods_signal", "2"],
        ["样本用户数", "10 月 3 日出现过的完整 18 位标识数", "dwd_signal.imsi", "2"],
        ["区县到访率", "当天在该区县基站出现过的用户 ÷ 样本用户", "dwd_signal.district", "2"],
        ["热点中心", "前 5 站点按连接用户数加权的重心", "dim_hotspot", "3"],
        ["热点到访率", "质心距中心 ≤ 半径的用户 ÷ 样本用户", "ads_hotspot_radius", "3"],
        ["到访人数", "半径内停留 ≥ 30 分钟的用户数", "ads_caliber_visitors", "4"],
        ["停留", "位置段持续 ≥ 30 分钟，半径 ≤ 500 米", "dws_stay", "5"],
        ["在场人数", "该小时有信令落在西塔 500 米内的用户", "ads_xita_hourly", "6"],
        ["首次出现占比", "该小时首次出现人数 ÷ 到过西塔人数", "ads_xita_hourly", "6"],
        ["西塔停留时长", "该人当天西塔停留时长之和，取中位", "dws_visitor.xita_stay_min", "7"],
        ["右删失比例", "到达某小时后 23:59 仍在西塔的人数占比", "ads_xita_censoring", "7"],
        ["过夜地", "与 0—6 点重叠 ≥ 60 分钟的最长停留位置", "dws_night", "8"],
        ["客群", "不明 → 外地 → 周边 → 市内，顺序判定", "dws_visitor_tag", "9"],
        ["商圈联动", "到达西塔前后在其他商圈的 ≥ 30 分钟停留", "ads_xita_linkage", "11"],
    ],
    [3.2, 7.4, 4.4, 1.6],
    first_left=True,
    size=10,
    cap="表 A-1  指标口径与证据索引",
)

# ── 附录 B ─────────────────────────────────────────────────────────────
h1("附录 B  图表与数据资产清单")
body_p(
    f"正文 {FIG_N[0]} 张图、{TAB_N[0] - 1} 张表全部由 image/ 目录下的 png 与 signal.db 的汇总表生成，"
    "表号与图号按正文出现顺序编排；本附录给出图与来源文件的对应关系，便于替换或复跑。"
)
table(
    "",
    ["图号", "结论", "文件"],
    [
        ["图 1", "三日记录 97.30% 集中在 10 月 3 日", "image/D01_01_各日记录分布.png"],
        ["图 2", "和平区 97.32%，康平县 0.32%", "image/D4_01_各区到访用户占比.png"],
        ["图 3", "西塔热点与 500 米范围", "image/D4_02_西塔热点.png"],
        ["图 4", "12 种口径相差 2.9 倍", "image/D7_01_到访人数口径对比.png"],
        ["图 5", "换站距离中位 666 米", "image/D6_02_站点切换距离.png"],
        ["图 6", "一个典型用户的一天", "image/D6_01_一个人的一天.png"],
        ["图 7", "半径不敏感、时长敏感", "image/D06_04_停留参数敏感性.png"],
        ["图 8", "17 点起在场人数翻倍", "image/D4_04_西塔在场与首次出现.png"],
        ["图 9", "22 点到的访客 97.79% 跨过 23 点", "image/D7_03_停留时长删失.png"],
        ["图 10", "过夜地中位距离 2.9 公里", "image/D7_04_过夜地距离.png"],
        ["图 11", "过夜地区县分布", "image/D7_05_过夜地分布.png"],
        ["图 12", "四类客群构成", "image/D8_01_傍晚访客客群.png"],
        ["图 13", "四类客群画像", "image/D07_01_西塔客群画像.png"],
        ["图 14", "外地来客口径修正", "image/D8_02_外地来客口径修正.png"],
        ["图 15", "三商圈联动", "image/D8_03_商圈联动.png"],
        ["图 16", "16 条稽核结论", "image/D5_03_数据质量检查汇总.png"],
    ],
    [2.0, 8.0, 6.0],
    first_left=True,
    size=10,
    cap="表 B-1  图表与来源文件对照",
)

end = doc.add_paragraph()
end.alignment = WD_ALIGN_PARAGRAPH.CENTER
end.paragraph_format.space_before = Pt(24)
_txt(end, "— 报告结束 —", size=10.5)

cp = doc.core_properties
cp.title = "沈阳移动信令数据分析报告"
cp.subject = "2018 年 10 月 3 日样本：国庆傍晚西塔访客的到访时刻、停留时长、来源与商圈联动"
cp.author = "signal-insight 项目"
cp.category = "数据分析报告"
cp.comments = "文档编号 DA-SY-20181003；数据来源为历史脱敏样本（2018 年国庆）。"
cp.keywords = "信令数据；停留识别；客群划分；商圈联动；西塔"

doc.save(str(OUT))
print("saved", OUT)
print("figures", FIG_N[0], "tables", TAB_N[0], "paragraphs", len(doc.paragraphs))
