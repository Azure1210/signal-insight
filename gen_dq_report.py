#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : gen_dq_report.py
# @Path       : signal-insight/gen_dq_report.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: 生成《沈阳移动信令数据质量分析报告.docx》（按 docs/图表规范.md 排版）。
"""生成《沈阳移动信令数据质量分析报告.docx》。

排版依据：
- 字体：只写开源字体（图表规范第 0 节，合规红线）——
  标题 Source Han Sans SC（思源黑体）、正文 Noto Serif SC（思源宋体）、西文 TeX Gyre Termes。
- 颜色：图表规范第 2 节的固定色板 —— 主色 #1D6FA5，状态色 通过 #3B8C66 / 警告 #B7791F / 不通过 #D64545。
- 插图：宽 15.4 厘米（A4 版心，图表规范第 8 节）；图注 = 结论式标题 + 口径副标题 + 来源行。
- 每张图表前有正文引导句解释，数字一律由聚合结果计算。
运行：python gen_dq_report.py
"""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import (WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING,
                             WD_TAB_ALIGNMENT, WD_TAB_LEADER)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
IMG = ROOT / "image"
OUT = ROOT / "沈阳移动信令数据质量分析报告.docx"

# ── 图表规范第 0 节：只用开源字体 ──
SANS = "Source Han Sans SC"    # 思源黑体（标题、表头、图注标题）——本机静态 otf，Word 渲染正常
SERIF = "Source Han Sans SC"   # 正文也暂用思源黑体：本机 Word（DirectWrite 字体缓存）识别不了
                               # Noto Serif CJK SC，会静默替换成别的字体、PDF 文本层错乱（"年"字）。
                               # 待字体缓存刷新 / 换机后，可改回 "Noto Serif CJK SC"（衬线正文）。
WEST = "TeX Gyre Termes"       # 西文衬线（正文西文、数字）

# ── 图表规范第 2 节：固定色板 ──
MAIN = RGBColor(0x1D, 0x6F, 0xA5)      # 主色：标题、表题、表头、页眉线、封面
MAIN_LIGHT_RGB = RGBColor(0xDC, 0xEA, 0xF5)   # 主色浅（封面副题用）
MAIN_LIGHT = "DCEAF5"                   # 主色浅（十六进制，段落底纹用）
ZEBRA = "EFF6FB"
BORDER = "BFBFBF"                       # 表格边框浅灰
INK = RGBColor(0x1F, 0x29, 0x37)        # 正文
MUTED = RGBColor(0x6B, 0x72, 0x80)      # 次要文字、图注副标题
FAINT = RGBColor(0x9C, 0xA3, 0xAF)      # 来源行
GREEN = RGBColor(0x3B, 0x8C, 0x66)      # 通过
AMBER = RGBColor(0xB7, 0x79, 0x1F)      # 警告
RED = RGBColor(0xD6, 0x45, 0x45)        # 不通过
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FIG_W = 15.4          # 图表规范第 8 节：报告插图宽 15.4 厘米（A4 版心）


# ───────────────────────── 基础工具 ─────────────────────────

def style_font(style, cn=SERIF, en=WEST, size=12, bold=False, color=INK):
    style.font.name = en
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    rpr.get_or_add_rFonts().set(qn("w:eastAsia"), cn)


def run_font(run, cn=SERIF, en=WEST, size=12, bold=False, color=INK):
    run.font.name = en
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), cn)


def add_field(paragraph, instr):
    """在段落里插入 Word 域（页码、目录等）。"""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    text = OxmlElement("w:instrText"); text.set(qn("xml:space"), "preserve"); text.text = instr
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    run._r.append(begin); run._r.append(text); run._r.append(end)


def shade_cell(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def shade_paragraph(paragraph, fill):
    p_pr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), fill)
    p_pr.append(shd)


def bottom_border(paragraph, color_hex, sz="18", space="4"):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), space); bottom.set(qn("w:color"), color_hex)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def set_table_borders(table, color=BORDER, size="4"):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single"); el.set(qn("w:sz"), size)
        el.set(qn("w:space"), "0"); el.set(qn("w:color"), color)
        borders.append(el)
    tbl_pr.append(borders)


def cell_text(cell, text, cn=SERIF, size=10.5, bold=False, color=INK,
              align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    para = cell.paragraphs[0]
    para.alignment = align
    para.paragraph_format.line_spacing = 1.15
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(2)
    run = para.add_run(str(text))
    run_font(run, cn=cn, size=size, bold=bold, color=color)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


STATUS_COLOR = {"通过": GREEN, "警告": AMBER, "不通过": RED}


def add_table(doc, headers, rows, widths, caption=None, size=10.5,
              col_align=None, first_col_left=False, status_col=None):
    """企业风格表格：主色表头白字、斑马纹、浅灰边框；表题用主色加粗。"""
    if caption:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.space_before = Pt(10)
        cp.paragraph_format.space_after = Pt(4)
        cp.paragraph_format.keep_with_next = True      # 表题不与表格分离
        run_font(cp.add_run(caption), cn=SANS, size=10.5, bold=True, color=MAIN)
    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.autofit = False
    set_table_borders(table)
    for j, w in enumerate(widths):
        table.columns[j].width = Cm(w)
        for cell in table.columns[j].cells:
            cell.width = Cm(w)
    for j, h in enumerate(headers):
        cell_text(table.rows[0].cells[j], h, cn=SANS, size=size, bold=True,
                  color=WHITE, align=WD_ALIGN_PARAGRAPH.CENTER)
        shade_cell(table.rows[0].cells[j], "1D6FA5")
    for i, row in enumerate(rows, start=1):
        for j, v in enumerate(row):
            align = WD_ALIGN_PARAGRAPH.CENTER
            if first_col_left and j == 0:
                align = WD_ALIGN_PARAGRAPH.LEFT
            elif col_align and j < len(col_align):
                align = col_align[j]
            color = INK
            bold = False
            if status_col is not None and j == status_col:
                color = STATUS_COLOR.get(str(v), INK)
                bold = True
            if first_col_left and j == 0:
                bold = True
            cell_text(table.rows[i].cells[j], v, size=size, bold=bold, color=color, align=align)
        if i % 2 == 0:                     # 斑马纹
            for cell in table.rows[i].cells:
                shade_cell(cell, ZEBRA)
    # 表头跨页重复 + 数据行不在页间断开（商业规范：一行要么在上页要么在下页）
    tr_pr = table.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); tr_pr.append(th)
    for row in table.rows:
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_figure(doc, name, title, subtitle, source):
    """图 = 正文引导句（调用方写）+ 图片（15.4cm 版心等宽）+ 三层图注。

    图注三层对应图表规范第 1 节的五部分（图片内已有标题区与标注）：
    结论式标题（含数字）/ 口径副标题 / 来源行。
    图与三层图注全部 keep_with_next，跨页时整体移动，不拆散。
    """
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(10)
    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.keep_with_next = True
    para.add_run().add_picture(str(IMG / name), width=Cm(FIG_W))
    t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.paragraph_format.space_before = Pt(4); t.paragraph_format.space_after = Pt(0)
    t.paragraph_format.keep_with_next = True
    run_font(t.add_run(title), cn=SANS, size=10.5, bold=True, color=INK)
    s = doc.add_paragraph(); s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s.paragraph_format.space_after = Pt(0)
    s.paragraph_format.keep_with_next = True
    run_font(s.add_run(subtitle), size=10.5, color=MUTED)
    src = doc.add_paragraph(); src.alignment = WD_ALIGN_PARAGRAPH.CENTER
    src.paragraph_format.space_after = Pt(10)
    run_font(src.add_run(source), size=8.5, color=FAINT)


def add_body(doc, text, indent=True, bold=False, space_after=6, keep_next=False):
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    para.paragraph_format.line_spacing = 1.5
    para.paragraph_format.space_after = Pt(space_after)
    if indent:
        para.paragraph_format.first_line_indent = Pt(24)   # 首行缩进 2 字符（小四）
    if keep_next:                                          # 图前引导句：整段不分页 + 与图绑定
        para.paragraph_format.keep_with_next = True
        para.paragraph_format.keep_together = True
    run = para.add_run(text)
    run_font(run, size=12, bold=bold)
    return para


# TOC 条目登记 + 书签（目录在文档末尾统一生成，再移动到文档控制页之后）
TOC_ENTRIES = []      # (level, text, bookmark)
_BM_ID = [0]


def add_h(doc, text, level):
    para = doc.add_heading(text, level=level)
    para.paragraph_format.space_before = Pt(13 if level == 1 else 10)
    para.paragraph_format.space_after = Pt(10 if level == 1 else 6)
    para.paragraph_format.line_spacing = 1.5
    for run in para.runs:
        run_font(run, cn=SANS, size={1: 16, 2: 14, 3: 12}[level], bold=True, color=MAIN)
    if level == 1:                     # 章标题：主色文字 + 主色底线；每章另起页（属性分页，不留空页）
        bottom_border(para, "1D6FA5", sz="18")
        para.paragraph_format.page_break_before = True
    bid = _BM_ID[0]; _BM_ID[0] += 1    # 书签：供目录 PAGEREF 引用页码
    bm = f"bm{bid}"
    start = OxmlElement("w:bookmarkStart"); start.set(qn("w:id"), str(bid)); start.set(qn("w:name"), bm)
    end = OxmlElement("w:bookmarkEnd"); end.set(qn("w:id"), str(bid))
    para._p.insert(0, start)
    para._p.append(end)
    TOC_ENTRIES.append((level, text, bm))
    return para


def page_break(doc):
    para = doc.add_paragraph()
    para.add_run().add_break(WD_BREAK.PAGE)
    return para


def set_page(section):
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.6)


# ───────────────────────── 文档构建 ─────────────────────────

doc = Document()

style_font(doc.styles["Normal"], size=12)
doc.styles["Normal"].paragraph_format.line_spacing = 1.5
for level in (1, 2, 3):
    style_font(doc.styles[f"Heading {level}"], cn=SANS,
               size={1: 16, 2: 14, 3: 12}[level], bold=True, color=MAIN)

sec1 = doc.sections[0]
set_page(sec1)

# ═══════════ 封面（第一节，无页眉页脚；主色横幅 + 信息区） ═══════════
# 整页内容必须正好一页：空段共 5 个，蓝块 4 段，信息表 7 行，底部 2 段 + 收尾线
for _ in range(2):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(14); p.paragraph_format.space_after = Pt(6)
run_font(p.add_run("信 令 数 据 分 析 项 目"), cn=SANS, size=14, bold=True, color=WHITE)
shade_paragraph(p, "1D6FA5")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(6)
run_font(p.add_run("沈阳移动信令数据质量分析报告"), cn=SANS, size=26, bold=True, color=WHITE)
shade_paragraph(p, "1D6FA5")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(12)
run_font(p.add_run("Signal Data Quality Analysis Report"), en=WEST, size=12, color=MAIN_LIGHT_RGB)
shade_paragraph(p, "1D6FA5")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(10)
run_font(p.add_run("2018 年国庆手机信令样本 · 数据接入与清洗阶段（D01–D05）"),
         cn=SERIF, size=12, color=WHITE)
shade_paragraph(p, "1D6FA5")
doc.add_paragraph()
info = [
    ("报告编号", "SIG-DQ-2026-001"),
    ("版    本", "V1.0"),
    ("密    级", "内部资料"),
    ("编 制 人", "AzureKite 1210"),
    ("审 核 人", ""),
    ("批 准 人", ""),
    ("编制日期", "2026 年 10 月 15 日"),
]
t = doc.add_table(rows=len(info), cols=2)
t.alignment = 1
for i, (k, v) in enumerate(info):
    t.rows[i].cells[0].width = Cm(4.2)
    t.rows[i].cells[1].width = Cm(7.0)
    cell_text(t.rows[i].cells[0], k, cn=SANS, size=12, bold=True, color=MAIN,
              align=WD_ALIGN_PARAGRAPH.CENTER)
    cell_text(t.rows[i].cells[1], v, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
for _ in range(2):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run_font(p.add_run("信令数据分析项目组"), cn=SERIF, size=12)
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(0)
run_font(p.add_run("2026 年 10 月"), cn=SERIF, size=12)
p = doc.add_paragraph()
bottom_border(p, "1D6FA5", sz="24")

# ═══════════ 第二节起：文档控制页 / 目录 / 正文（页眉页脚） ═══════════
sec2 = doc.add_section(WD_SECTION.NEW_PAGE)
set_page(sec2)
sec2.header.is_linked_to_previous = False
sec2.footer.is_linked_to_previous = False
hp = sec2.header.paragraphs[0]
hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
run_font(hp.add_run("沈阳移动信令数据质量分析报告"), cn=SANS, size=9, color=MUTED)
bottom_border(hp, "1D6FA5", sz="8", space="2")
fp = sec2.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
run_font(fp.add_run("第 "), size=9, color=MUTED)
add_field(fp, "PAGE")
run_font(fp.add_run(" 页  共 "), size=9, color=MUTED)
add_field(fp, "NUMPAGES")
run_font(fp.add_run(" 页"), size=9, color=MUTED)

# ── 文档控制页 ──
add_h(doc, "文档控制", 1)
add_body(doc, "文档修订记录", indent=False, bold=True, space_after=4)
add_table(doc,
          ["版本", "日期", "修订说明", "编制", "审核"],
          [["V1.0", "2026-10-15", "初稿：基于 D01–D05 阶段数据接入、验收、清洗与流水线建设成果编制", "AzureKite", ""]],
          [2.0, 2.6, 7.0, 2.0, 1.6])
add_body(doc, "编制与审核", indent=False, bold=True, space_after=4)
add_table(doc,
          ["角色", "姓名", "签字", "日期"],
          [["编制", "AzureKite 1210", "", "2026-10-15"],
           ["审核", "", "", ""],
           ["批准", "", "", ""]],
          [2.4, 4.0, 4.0, 3.0])
add_body(doc, "分发范围：项目组内部存档；涉及数据提供方的事项见第 9 章反馈清单。", space_after=0)
PB_PARA = doc.add_paragraph()   # 目录的锚点：目录在文档末尾生成后移动到它后面；分页由目录标题的 page_break_before 负责

# ── 执行摘要 ──
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(12)
p.paragraph_format.page_break_before = True
run_font(p.add_run("执行摘要"), cn=SANS, size=18, bold=True, color=MAIN)
bottom_border(p, "1D6FA5")
add_body(doc, "本报告对 2018 年国庆期间采集的沈阳移动手机信令样本（532,828 行原始记录）"
              "开展数据质量分析与评估，覆盖数据接入（D01）、数据验收（D02）、空间维度检查（D03）、"
              "样本结构检查（D04）与数据流水线建设（D05）五个阶段，共执行 16 项质量检查，"
              "其中 5 项通过、6 项警告、5 项不通过；不通过项均已通过删除、弃用或更换口径等方式完成处理。")
add_body(doc, "原始数据整体质量良好：关键字段缺失率不足 0.01%，信令与基站表关联率达 99.998%，"
              "经过四步清洗共剔除 16,897 行（占 3.17%），产出明细表 dwd_signal 515,931 行、"
              "5,644 个用户。经校验确认，用户主键应采用完整 18 位 IMSI（冲突为 0），"
              "前 15 位截断主键会使 15.6% 的“用户”对应多个手机号，不能使用。")
add_body(doc, "需要重点关注的结论边界有三项：其一，样本圈选口径疑似为“10 月 3 日傍晚后到访西塔的"
              "人群”，97.3% 的用户到过和平区、86% 到过西塔 500 米以内，结论不可外推至全市或全天；"
              "其二，样本全部为中国移动用户，人数推算需按市场份额扩样；"
              "其三，nid 事件类型字典与数据实际行为不符，nid 含义暂标为未知。"
              "上述事项已列入第 9 章向数据提供方的反馈清单。")
add_body(doc, "关键数字一览", indent=False, bold=True, space_after=4)
add_table(doc,
          ["指标", "数值", "指标", "数值"],
          [["原始记录数", "532,828 行", "清洗剔除", "16,897 行（3.17%）"],
           ["分析日期范围", "2018-10-03（占 97.3%）", "明细表行数 / 用户数", "515,931 行 / 5,644 个"],
           ["字段缺失（关键字段）", "imsi 15 行、lac_id 4 行、cell_id 5 行", "信令-基站关联率", "99.998%"],
           ["主键确认", "18 位 IMSI，冲突 0", "质量检查", "16 项：通过 5 / 警告 6 / 不通过 5"]],
          [3.6, 3.6, 3.6, 3.6], size=10, first_col_left=True)

# ═══════════ 1 概述 ═══════════
add_h(doc, "1  概述", 1)
add_h(doc, "1.1  报告目的", 2)
add_body(doc, "本报告旨在系统记录沈阳移动信令样本从接入到清洗全过程的数据质量评估结果，"
              "回答三个问题：数据能否用于回答“国庆傍晚来西塔的人几点来、待多久、从哪来、还去了哪”；"
              "哪些问题已处理、以什么方式处理；哪些问题需要向数据提供方反馈。"
              "报告同时作为 D01–D05 阶段数据质量工作的正式交付物归档。")
add_h(doc, "1.2  适用范围", 2)
add_body(doc, "本报告覆盖原始层（ods_*）与明细层（dwd_signal）的 8 张相关表："
              "ods_signal、ods_cell、ods_nid_mapping、ods_aoi_v1、ods_aoi_v2、ods_aoi_json、"
              "ods_district_boundary 及清洗产出的 dwd_signal、dim_cell、dim_hotspot。"
              "分析范围为 2018-10-03 一天的数据（依据见 2.3 节）。")
add_h(doc, "1.3  评估依据", 2)
add_body(doc, "本报告的质量维度参考 GB/T 36344-2018《信息技术 数据质量评价指标》中的规范性、"
              "完整性、准确性、一致性、时效性维度，并结合信令数据分析的实际需要，"
              "增加唯一性（主键可辨识）与代表性（样本可外推）两个维度。"
              "检查规则、判定阈值与处理决定统一记录于 dq_check_result 稽核表，"
              "每项检查均可追溯证据（见第 8 章）。")
add_h(doc, "1.4  术语", 2)
add_body(doc, "IMSI：国际移动用户识别码，本数据中为 18 位数字串，是本项目的用户主键。"
              "lac_id / cell_id：位置区编号 / 小区编号，二者拼接为 lac_cell 扇区键，用于关联基站表。"
              "ODS / DWD / DIM：原始层 / 明细层 / 维度层，为数据仓库分层约定（AGENTS.md 第 5 条）。"
              "稽核记录：写入 dq_check_result 表的质量检查结论，同一检查项重跑覆盖旧记录。")

# ═══════════ 2 数据概况 ═══════════
add_h(doc, "2  数据概况", 1)
add_h(doc, "2.1  数据源与采集", 2)
add_body(doc, "数据由数据提供方从移动信令平台导出，为 2018 年国庆假期（10 月 1 日至 10 月 3 日）"
              "的脱敏信令样本，共 532,828 行、10 个字段，属事件触发型记录而非定时采样。"
              "伴随提供的基础数据还包括：基站表（ods_cell，49,954 行）、事件类型字典（ods_nid_mapping）、"
              "商圈边界三个版本（ods_aoi_v1 / v2 / json）与区县边界（ods_district_boundary）。")
add_h(doc, "2.2  数据规模与字段结构", 2)
add_body(doc, "原始信令表 ods_signal 共 10 个字段，结构如下：")
add_table(doc,
          ["字段", "类型", "含义", "质量备注"],
          [["timestamp", "INTEGER", "事件时间，UTC 毫秒", "北京时间 = 加 8 小时"],
           ["imsi", "TEXT", "用户标识", "完整 18 位才是一个人"],
           ["lac_id", "REAL", "位置区编号", "库中为浮点（列内有空值）"],
           ["cell_id", "REAL", "小区编号", "同上"],
           ["phone", "TEXT", "脱敏手机号", "14 位；6666 为占位值"],
           ["timestamp1", "INTEGER", "第二时间戳", "与 timestamp 中位差 23 毫秒"],
           ["tmp0 / tmp1", "REAL/TEXT", "无内容", "100% 为空，已删除"],
           ["nid", "INTEGER", "事件类型编码", "字典不可信（DQ-09）"],
           ["npid", "TEXT", "掩码编号", "形如 #*#6137"]],
          [2.6, 2.0, 4.2, 5.4], size=10, caption="表 2-1  ods_signal 字段结构",
          first_col_left=True)
add_h(doc, "2.3  时间分布与时效性", 2)
add_body(doc, "按日统计，97.3% 的记录集中在 10 月 3 日；10 月 1 日仅 54 条，10 月 2 日为 1.4 万条"
              "零散记录（表 2-2）。这一分布不符合“完整采集三天”的预期，属于时效性问题（DQ-01），"
              "经与项目目标核对，分析范围限定为 2018-10-03 单日。")
add_table(doc,
          ["日期", "记录数", "记录占比", "用户数", "备注"],
          [["10-01", "54", "0.01%", "53", "仅零散样本"],
           ["10-02", "14,331", "2.69%", "4,046", "零散记录，不完整"],
           ["10-03", "518,443", "97.3%", "5,652", "分析范围"],
           ["合计", "532,828", "100.0%", "—", "—"]],
          [2.6, 2.6, 2.6, 2.6, 3.6], size=10, caption="表 2-2  各日记录分布")
add_body(doc, "如图 2-1 所示，三天的记录量差距悬殊：10 月 3 日的记录数约为其余两天之和的 36 倍，"
              "单日分析口径因此成立。", keep_next=True)
add_figure(doc, "D01_01_各日记录分布.png",
           "图 2-1  10 月 3 日记录占 97.3%，分析范围限定为单日",
           "各日原始记录数与占比（10-01 至 10-03）；单日口径下 10-03 为 518,443 行",
           "数据来源：ods_signal 聚合（ads_daily_volume）")

# ═══════════ 3 质量评估体系 ═══════════
add_h(doc, "3  质量评估体系", 1)
add_h(doc, "3.1  评估维度", 2)
add_body(doc, "参照 GB/T 36344-2018 并结合本项目需要，共设置 7 个评估维度：")
add_table(doc,
          ["维度", "定义", "本项目中的应用"],
          [["完整性", "数据字段与记录是否齐全、无缺失", "字段缺失率检查、整列为空检查"],
           ["唯一性", "主键能否唯一标识实体", "IMSI 主键校验、完全重复记录检查"],
           ["一致性", "同一信息在多处表达是否一致", "双时间戳比对、信令与基站关联"],
           ["准确性", "数据与真实世界是否相符", "nid 字典与行为比对、商圈边界核对"],
           ["规范性", "数据是否符合既定格式规范", "IMSI 18 位纯数字、手机号、坐标单位"],
           ["时效性", "数据是否满足时间要求", "各日覆盖度检查"],
           ["代表性", "样本能否代表目标总体", "圈选口径、运营商覆盖检查"]],
          [2.0, 5.4, 6.8], size=10, caption="表 3-1  质量评估维度定义", first_col_left=True)
add_h(doc, "3.2  评估方法", 2)
add_body(doc, "采用三种方法交叉验证：（1）规则校验——按既定格式与阈值逐行检查，"
              "如 IMSI 是否为 18 位纯数字；（2）分布检查——按日、小时、区县等维度观察分布形态，"
              "识别异常峰值与缺口；（3）交叉验证——将同一信息在不同表中的表达互相比对，"
              "如事件字典与信令行为、信令扇区与基站表坐标。")
add_h(doc, "3.3  稽核记录机制", 2)
add_body(doc, "每项检查的结论以统一结构写入 dq_check_result 表（check_id、维度、检查项、表字段、"
              "结果、状态、证据、处理决定），同一 check_id 重跑覆盖旧记录。"
              "数据流水线（pipeline.py）的每次运行另写入 etl_log 运行日志，"
              "记录每一步的输入/输出行数与耗时，保证结果可追溯、可重跑。")

# ═══════════ 4 质量检查结果 ═══════════
add_h(doc, "4  质量检查结果", 1)
add_h(doc, "4.1  完整性", 2)
add_body(doc, "字段级缺失检查（表 4-1）发现：tmp0、tmp1 两列 100% 为空（DQ-02，不通过），"
              "已整列删除；关键字段 imsi、lac_id、cell_id 合计缺失 24 行，占比不足 0.01%（DQ-03，通过），"
              "已整行删除。基站表 49,954 行中有 6 行缺坐标（DQ-10，通过），已删除。")
add_table(doc,
          ["字段", "缺失数", "缺失率", "判定", "处理"],
          [["tmp0", "532,828", "100.0%", "不通过", "整列删除"],
           ["tmp1", "532,828", "100.0%", "不通过", "整列删除"],
           ["imsi", "15", "0.0028%", "通过", "整行删除"],
           ["lac_id", "4", "0.0008%", "通过", "整行删除"],
           ["cell_id", "5", "0.0009%", "通过", "整行删除"],
           ["timestamp / phone / timestamp1 / nid / npid", "0", "0.00%", "通过", "—"]],
          [4.6, 2.2, 2.2, 2.2, 3.0], size=10, caption="表 4-1  ods_signal 字段缺失统计",
          status_col=3)
add_body(doc, "如图 4-1 所示，除 tmp0、tmp1 外其余字段缺失率均低于 0.01%，"
              "数据完整性问题集中在两列全空字段上，处理成本低。", keep_next=True)
add_figure(doc, "D3_01_字段缺失率.png",
           "图 4-1  tmp0/tmp1 两列全空，其余字段缺失率不足 0.01%",
           "ods_signal 各字段缺失率；tmp0 全部为空值、tmp1 全部为空格",
           "数据来源：ods_signal 数据画像（ads_missing_by_field）；稽核 DQ-02 / DQ-03")
add_h(doc, "4.2  唯一性", 2)
add_body(doc, "完全重复检查（DQ-06）发现 2,568 行所有字段完全相同（占 0.48%），"
              "疑似采集或入库时重复写入，每组保留一条。主键检查（DQ-08，不通过）发现："
              "若以 IMSI 前 15 位作为用户主键，有 729 组（15.6%）对应多个手机号，"
              "牵连 1,707 个 18 位 IMSI（占 30.2%）；而完整 18 位 IMSI 与手机号一一对应、冲突为 0。"
              "如图 4-2 所示，前 15 位截断会把 15.6% 的“用户”张冠李戴，"
              "据此用户主键确定为完整 18 位 IMSI（详见 5.4 节）。", keep_next=True)
add_figure(doc, "D03_02_IMSI截断冲突.png",
           "图 4-2  前 15 位主键 15.6% 对应多个手机号，不能作为用户主键",
           "按 IMSI 前 15 位分组的手机号对应关系；729 组（15.6%）对应多个手机号",
           "数据来源：ods_signal 交叉校验（ads_key_check）；稽核 DQ-08")
add_h(doc, "4.3  一致性", 2)
add_body(doc, "双时间戳比对（DQ-07，通过）：timestamp 与 timestamp1 的中位差为 23 毫秒，"
              "99% 的记录差值在 1.3 秒以内，仅 9 行为负值；统一采用 timestamp 作为事件时间，"
              "差异对分钟级分析无影响（差值分布见图 4-3）。信令与基站表关联（DQ-11，通过）："
              "信令使用 19,787 个扇区，仅 8 个关联不到坐标（2 个基站表中无编号、6 个缺坐标），"
              "按记录计关联率为 99.998%。", keep_next=True)
add_figure(doc, "D03_05_lag分布.png",
           "图 4-3  双时间戳中位差 23 毫秒，99% 的记录在 1.3 秒以内",
           "timestamp 与 timestamp1 差值分布；仅 9 行为负值，不影响分钟级分析",
           "数据来源：ods_signal 比对；稽核 DQ-07")
add_h(doc, "4.4  准确性", 2)
add_body(doc, "事件类型字典核对（DQ-09，不通过）：字典标为“会话类事件”的 nid=5，有 51% 的记录伴随"
              "位置区变化，而全部记录的平均值仅 18%；字典标为“位置更新”的 nid=2 反而只有 12%。"
              "字典与实际行为明显不符，已弃用，nid 含义暂标为未知。商圈边界核对（DQ-13，不通过）："
              "v1 版本中太原街商圈面积自相交、未包含太原街地铁站，且沈阳北站存在一个经度写成 23.45 "
              "的错误顶点，已弃用 v1、采用 v2 版本。")
add_h(doc, "4.5  规范性", 2)
add_body(doc, "IMSI 格式检查（DQ-04）：发现 8 行含 * ^ # 等掩码字符，长度虽为 18 但不是纯数字，"
              "疑似脱敏处理失误，已删除并列入反馈清单。手机号检查（DQ-05）：36 行为占位值 6666"
              "（涉及 14 个 IMSI），其余均为 14 位；手机号不参与分析、明细表不保留该字段。"
              "商圈边界 json 版本（DQ-14，不通过）数值远超经纬度范围，需换算坐标系方可使用，"
              "本阶段不采用。")
add_h(doc, "4.6  时效性", 2)
add_body(doc, "各日覆盖度检查（DQ-01）已在 2.3 节说明：10 月 1 日仅 54 条、10 月 2 日 1.4 万条零散记录，"
              "判定为采集不完整（警告），分析范围限定为 2018-10-03。")
add_h(doc, "4.7  代表性", 2)
add_body(doc, "样本圈选口径检查（DQ-15，警告）：97.3% 的用户到过和平区、86% 到过西塔 500 米以内，"
              "热点在场人数 17 点后猛增、首次出现时间在 16→17 点跳升过陡，均指向样本为"
              "“10 月 3 日傍晚后到访西塔的人群”，而非全市随机样本。运营商覆盖检查（DQ-16，警告）："
              "IMSI 运营商代码仅出现 00、02、07，样本全部为中国移动用户。"
              "两项限制对应的结论边界见第 7 章。")

# ═══════════ 5 数据清洗处理记录 ═══════════
add_h(doc, "5  数据清洗处理记录", 1)
add_h(doc, "5.1  清洗规则", 2)
add_body(doc, "清洗按 D02 阶段确认的固定顺序执行，每步记录剔除行数与剩余行数，"
              "与 dq_check_result 的处理决定一一对应：")
add_body(doc, "（1）删除整列为空的 tmp0、tmp1 两列（对应 DQ-02）；"
              "（2）删除 imsi、lac_id、cell_id 任一缺失的行（DQ-03）；"
              "（3）删除 IMSI 非 18 位纯数字的行（DQ-04）；"
              "（4）按全部原始字段去重，每组完全重复的记录保留一条（DQ-06）；"
              "（5）仅保留 2018-10-03 当天的记录（DQ-01）。", indent=False)
add_h(doc, "5.2  清洗剔除明细", 2)
add_body(doc, "四步共剔除 16,897 行（占 3.17%），其中“非 10 月 3 日”的剔除占 2.68 个百分点，"
              "是剔除量最大的步骤（表 5-1）。")
add_table(doc,
          ["步骤", "剔除行数", "剩余行数", "剔除占比", "对应稽核项"],
          [["缺 imsi / lac / cell", "24", "532,804", "0.0045%", "DQ-03"],
           ["IMSI 格式异常", "8", "532,796", "0.0015%", "DQ-04"],
           ["完全重复", "2,568", "530,228", "0.48%", "DQ-06"],
           ["不是 10 月 3 日", "14,297", "515,931", "2.68%", "DQ-01"],
           ["合计", "16,897", "515,931", "3.17%", "—"]],
          [4.0, 2.4, 2.6, 2.6, 2.6], size=10, caption="表 5-1  清洗步骤剔除明细")
add_body(doc, "剔除构成如图 5-1 所示：非分析日记录占剔除量的 85%，说明清洗主要在做"
              "“收窄分析范围”而非“修补脏数据”，原始数据的脏数据比例很低。", keep_next=True)
add_figure(doc, "D03_04_清洗剔除明细.png",
           "图 5-1  清洗共剔除 16,897 行（3.17%），其中 85% 为非分析日记录",
           "四步剔除行数与占比；脏数据类剔除仅占剔除量的 15%",
           "数据来源：清洗流水线运行记录（ads_clean_steps）")
add_h(doc, "5.3  清洗结果", 2)
add_body(doc, "清洗后产出明细表 dwd_signal 515,931 行、5,644 个用户（18 位 IMSI 口径），"
              "仅保留分析日 2018-10-03 的记录。时间统一转为北京时间并固定存储格式，"
              "lac_id、cell_id 由浮点转为整数并拼接为 lac_cell 扇区键；"
              "记录按 (imsi, ts) 排序，同一用户的记录在时间上相邻，供后续停留识别使用。"
              "清洗结果写入按日期分区的 dwd_signal 表，同一天重跑结果一致（幂等）。")
add_h(doc, "5.4  主键确认", 2)
add_body(doc, "主键校验对比（表 5-2）确认：前 15 位截断主键存在大量多对一冲突，不能代表一个人；"
              "完整 18 位 IMSI 与手机号一一对应，冲突为 0，确定为项目用户主键。")
add_table(doc,
          ["分组方式", "ID 个数", "对应多个手机号的 ID", "占比", "结论"],
          [["按前 15 位", "4,667", "729", "15.6%", "不能代表一个人，弃用"],
           ["按完整 18 位", "5,645", "0", "0.0%", "与手机号一一对应，采用"]],
          [3.4, 2.6, 3.6, 2.0, 4.0], size=10, caption="表 5-2  用户主键分组校验（DQ-08）")

# ═══════════ 6 关联质量与空间维度质量 ═══════════
add_h(doc, "6  关联质量与空间维度质量", 1)
add_h(doc, "6.1  信令与基站表关联", 2)
add_body(doc, "信令明细通过 lac_cell 扇区键与基站表关联，按记录计关联率为 99.998%（DQ-11，通过）。"
              "关联不上的 8 个扇区中，2 个在基站表中无编号、其余 6 个缺坐标，"
              "相关记录在空间分析中剔除，影响可忽略。")
add_h(doc, "6.2  站点结构与地理范围", 2)
add_body(doc, "按坐标归并后，基站表 49,948 个扇区对应 14,106 个站点；单站最常见的形态是"
              "挂 3 个扇区（5,373 站，占 38.1%），其次为单扇区站点（3,536 站，占 25.1%），"
              "分布如图 6-1 所示。地理范围检查（DQ-12，通过）发现 34% 的站点位于沈阳市外，"
              "市外站点予以保留，区县标注为“市外”。", keep_next=True)
add_figure(doc, "D3_01_站点扇区数.png",
           "图 6-1  14,106 个站点中 38.1% 挂 3 个扇区，25.1% 为单扇区",
           "站点扇区数分布；单站最多 60 个扇区，长尾为基站集中挂载",
           "数据来源：ods_cell 按坐标归并（ads_sectors_per_site）")
add_body(doc, "市外站点虽多，但发生在市外站点的信令仅占 1.8%，对分析影响有限（图 6-2）。",
         keep_next=True)
add_figure(doc, "D3_02_站点与区县.png",
           "图 6-2  34% 站点在市外，但市外信令仅占 1.8%",
           "站点与区县的空间分布；市外站点予以保留、区县标为“市外”",
           "数据来源：dim_cell、dwd_signal；稽核 DQ-12")
add_body(doc, "维表 dim_cell 按区县的扇区分布如表 6-1，与站点到访占比（表 7-1）相互印证："
              "铁西、浑南、沈河为扇区最多的城区。")
add_table(doc,
          ["区县", "扇区数", "区县", "扇区数"],
          [["市外", "15,211", "于洪区", "2,708"],
           ["铁西区", "4,027", "沈北新区", "2,634"],
           ["浑南区", "3,974", "新民市", "1,972"],
           ["沈河区", "3,654", "苏家屯区", "1,949"],
           ["大东区", "3,448", "法库县", "1,719"],
           ["和平区", "3,109", "康平县", "1,396"],
           ["皇姑区", "2,754", "辽中区", "1,393"]],
          [2.6, 2.4, 2.6, 2.4], size=10, caption="表 6-1  dim_cell 区县扇区分布（共 49,948 扇区）")
add_h(doc, "6.3  边界数据质量", 2)
add_body(doc, "商圈边界三个版本经核对（DQ-13、DQ-14）：v1 存在多边形自相交与错误顶点，弃用；"
              "json 版本坐标系不明，不使用；采用 v2 版本。区县边界数据未发现异常，正常使用。")

# ═══════════ 7 样本代表性与结论边界 ═══════════
add_h(doc, "7  样本代表性与结论边界", 1)
add_h(doc, "7.1  样本圈选口径", 2)
add_body(doc, "区县到访分布（表 7-1）显示：97.3% 的用户到过和平区，沈河、皇姑、铁西在"
              "51%–57% 之间，而远郊四区县（新民、辽中、法库、康平）均不足 5%，"
              "最高与最低相差 305 倍，样本不是全市随机样本。")
add_table(doc,
          ["区县", "到访用户占比", "区县", "到访用户占比"],
          [["和平区", "97.3%", "大东区", "31.2%"],
           ["沈河区", "56.9%", "浑南区", "25.3%"],
           ["皇姑区", "54.5%", "沈北新区", "10.3%"],
           ["铁西区", "51.5%", "苏家屯区", "10.1%"],
           ["于洪区", "31.5%", "新民市", "4.7%"],
           ["辽中区", "3.3%", "法库县", "0.8%"],
           ["康平县", "0.3%", "—", "—"]],
          [2.8, 3.2, 2.8, 3.2], size=10, caption="表 7-1  各区县到访用户占比（n = 5,644）")
add_body(doc, "如图 7-1 所示，和平区一家独大、远郊四区县几乎为零的分布形态，"
              "是圈选口径问题的直接证据。", keep_next=True)
add_figure(doc, "D3_04_区县到访占比.png",
           "图 7-1  97.3% 的用户到过和平区，远郊四区县不足 5%",
           "各区县到访用户占比（n = 5,644）；最高为最低的 305 倍，非全市随机样本",
           "数据来源：dwd_signal 聚合（ads_district_reach）；稽核 DQ-15")
add_body(doc, "热点定位结果为西塔商圈（韩百商场、鑫韩城一带），86% 的用户到过热点 500 米以内"
              "（300 米 72.1%、1 公里 93.6%、2 公里 97.8%）。西塔在场人数 17 点后猛增"
              "（17 点 1,254 人 → 19 点 2,126 人），且 41% 的用户首次出现在 17–19 点，"
              "16→17 点跳升过陡（图 7-2），进一步印证样本为“10 月 3 日傍晚后到访西塔的人群"
              "及其全天信令”（DQ-15）。", keep_next=True)
add_figure(doc, "D4_04_西塔在场与首次出现.png",
           "图 7-2  西塔在场人数 17 点后猛增，41% 的用户首次出现在 17–19 点",
           "西塔 500 米内在场人数与首次出现人数按小时；16→17 点跳升过陡",
           "数据来源：dwd_signal 聚合（ads_xita_hourly）；稽核 DQ-15")
add_h(doc, "7.2  运营商覆盖", 2)
add_body(doc, "IMSI 运营商代码仅出现 00、02、07，样本全部为中国移动用户（DQ-16，警告）。"
              "据此，报告中的“人数”仅代表移动用户；如需推算全市总人数，需按移动市场份额扩样，"
              "或补充其他运营商的样本。")
add_h(doc, "7.3  结论适用边界", 2)
add_body(doc, "基于上述两项限制，本数据可以回答“国庆 10 月 3 日傍晚来西塔的移动用户几点来、"
              "待多久、从哪来、还去了哪”，但不能回答“西塔白天有多少人”或“全市客流总量”。"
              "对外输出（报告、图表、汇报）一律采用上述口径并注明来源。")

# ═══════════ 8 数据质量稽核汇总 ═══════════
add_h(doc, "8  数据质量稽核汇总", 1)
add_h(doc, "8.1  状态统计", 2)
add_body(doc, "本阶段共执行 16 项质量检查，状态分布为：通过 5 项、警告 6 项、不通过 5 项（表 8-1）。"
              "全部不通过项均已通过删除、弃用或更换口径完成处理，无未决问题。")
add_table(doc,
          ["状态", "条数", "占比", "说明"],
          [["通过", "5", "31.3%", "缺陷低于阈值，或已按既定规则处理"],
           ["警告", "6", "37.5%", "不影响本阶段分析，但需关注或向数据提供方确认"],
           ["不通过", "5", "31.3%", "已处理：删除 / 弃用 / 更换口径（详见明细）"],
           ["合计", "16", "100.0%", "—"]],
          [2.4, 2.0, 2.0, 8.0], size=10, caption="表 8-1  稽核状态统计",
          first_col_left=True, status_col=0)
add_h(doc, "8.2  稽核明细", 2)
add_body(doc, "16 项检查的完整记录如下（证据与处理决定全文保存在 dq_check_result 表，可追溯）：")
dq_rows = [
    ["DQ-01", "时效性", "各日数据完整度", "10月3日占97.3%", "警告", "分析范围限定为 2018-10-03"],
    ["DQ-02", "完整性", "整列为空的字段", "tmp0/tmp1 两字段100%为空", "不通过", "删除这两个字段"],
    ["DQ-03", "完整性", "关键字段缺失", "24行（不足0.01%）", "通过", "删除这些行"],
    ["DQ-04", "规范性", "IMSI 格式", "8行含掩码字符", "警告", "删除并反馈数据提供方"],
    ["DQ-05", "规范性", "手机号格式", "36行为占位值6666", "警告", "不用于分析，明细表不保留"],
    ["DQ-06", "唯一性", "完全重复记录", "2,568行（0.48%）", "警告", "每组只保留一条"],
    ["DQ-07", "一致性", "两个时间戳的差", "中位23毫秒，99%在1.3秒内", "通过", "统一用 timestamp"],
    ["DQ-08", "唯一性", "用户主键", "前15位15.6%对应多手机号", "不通过", "主键改用完整18位IMSI"],
    ["DQ-09", "准确性", "nid字典与数据行为", "nid=5有51%伴随位置区变化", "不通过", "字典不采用，向提供方索取文档"],
    ["DQ-10", "完整性", "基站坐标缺失", "6行（不足0.02%）", "通过", "删除这6行"],
    ["DQ-11", "一致性", "信令与基站关联率", "按记录99.998%", "通过", "关联不上的在空间分析中剔除"],
    ["DQ-12", "代表性", "基站表的地理范围", "34%站点在市外", "通过", "保留，区县标为市外"],
    ["DQ-13", "准确性", "商圈边界v1", "太原街面积自相交", "不通过", "弃用v1，采用v2"],
    ["DQ-14", "规范性", "商圈json版坐标单位", "数值远超经纬度范围", "不通过", "不使用，向提供方确认坐标系"],
    ["DQ-15", "代表性", "样本圈选口径", "97%到过和平区，86%到过西塔500米内", "警告", "结论限定口径，向提供方确认取数条件"],
    ["DQ-16", "代表性", "运营商覆盖", "全部为中国移动用户", "警告", "按移动市场份额扩样后再推算总量"],
]
add_table(doc,
          ["编号", "维度", "检查项", "结果", "状态", "处理决定"],
          dq_rows,
          [1.4, 1.6, 3.0, 3.6, 1.6, 3.4], size=9, caption="表 8-2  数据质量稽核明细（16 项）",
          first_col_left=True, status_col=4)
add_h(doc, "8.3  汇总视图", 2)
add_body(doc, "16 项检查按维度的状态分布汇总见图 8-1：不通过项集中在准确性（2 项）、规范性（1 项）、"
              "唯一性（1 项）与完整性（1 项），均已闭环处理；警告项以代表性问题（3 项）为主，"
              "属于样本本身的口径限制，而非数据缺陷。", keep_next=True)
add_figure(doc, "D5_03_数据质量检查汇总.png",
           "图 8-1  16 项检查全部闭环：通过 5、警告 6、不通过 5",
           "按质量维度的检查状态分布；红色（不通过）项均已按处理决定执行完毕",
           "数据来源：dq_check_result 稽核表")

# ═══════════ 9 结论与建议 ═══════════
add_h(doc, "9  结论与建议", 1)
add_h(doc, "9.1  总体质量评价", 2)
add_body(doc, "总体评价：数据质量良好，可支撑既定分析目标。原始数据关键字段缺失率不足 0.01%，"
              "信令与基站关联率 99.998%，清洗过程剔除 3.17% 的记录后未发现影响结论的残余问题。"
              "16 项质量检查全部闭环：通过项留档备查，不通过项已按处理决定执行，"
              "警告项均不影响本阶段分析且已列入跟踪。")
add_body(doc, "质量保障已固化进流水线：清洗规则、维表构建与质量稽核均写入代码"
              "（dwd.py / dims.py / quality.py / pipeline.py），并有 78 个自动化测试"
              "（契约测试 24 个 + 单元测试 54 个）锁定各模块对下游的承诺；"
              "每日运行写入 etl_log，行数与耗时可追溯。")
add_h(doc, "9.2  向数据提供方的反馈清单", 2)
add_body(doc, "以下事项建议向数据提供方反馈确认：")
add_table(doc,
          ["序号", "事项", "涉及稽核项", "建议"],
          [["1", "8 行 IMSI 含 * ^ # 掩码字符", "DQ-04", "确认脱敏规则，修正或说明"],
           ["2", "nid 事件类型字典与数据实际行为不符", "DQ-09", "索取事件类型接口文档"],
           ["3", "样本圈选口径未说明（疑似西塔傍晚人群）", "DQ-15", "确认取数条件与筛选逻辑"],
           ["4", "商圈 json 版本坐标系不明", "DQ-14", "确认坐标系与投影参数"],
           ["5", "36 行手机号为占位值 6666", "DQ-05", "确认脱敏占位规则"],
           ["6", "样本仅覆盖中国移动用户", "DQ-16", "如需总量口径，补充其他运营商样本"]],
          [1.2, 5.6, 2.2, 5.2], size=10, caption="表 9-1  向数据提供方反馈清单", first_col_left=True)
add_h(doc, "9.3  后续工作", 2)
add_body(doc, "（1）按反馈清单与数据提供方逐项确认，收到答复后更新对应稽核记录；"
              "（2）D06 起开展停留识别与汇总层（dws_）建设，继续沿用本报告的稽核机制；"
              "（3）每次流水线运行后核对 etl_log 行数与本报告基准（515,931 行）的一致性，"
              "出现偏差即触发质量复查。")

# ═══════════ 附录 A 字段字典 ═══════════
add_h(doc, "附录 A  字段字典", 1)
add_body(doc, "本报告涉及的主要表结构如下（完整字典见 docs/数据字典.md）：")
dict_rows = [
    ["ods_signal", "timestamp", "INTEGER", "事件时间，UTC 毫秒（+8 小时为北京时间）"],
    ["ods_signal", "imsi", "TEXT", "用户标识，完整 18 位才是一个人"],
    ["ods_signal", "lac_id / cell_id", "REAL", "位置区 / 小区编号（库中为浮点，清洗后转整数）"],
    ["ods_signal", "phone", "TEXT", "脱敏手机号（14 位，6666 为占位值）"],
    ["ods_signal", "timestamp1", "INTEGER", "第二时间戳（与 timestamp 中位差 23 毫秒）"],
    ["ods_signal", "tmp0 / tmp1", "REAL / TEXT", "无内容（100% 为空，已删除）"],
    ["ods_signal", "nid / npid", "INTEGER / TEXT", "事件类型编码 / 掩码编号"],
    ["dwd_signal", "imsi / ts / dt", "TEXT", "用户标识 / 北京时间 / 日期分区 2018-10-03"],
    ["dwd_signal", "lac_id / cell_id", "INTEGER", "位置区 / 小区编号（整数）"],
    ["dwd_signal", "nid", "INTEGER", "事件类型编码（含义未知，原样保留）"],
    ["dwd_signal", "lac_cell", "TEXT", "扇区键 lac_id-cell_id，用于关联基站表"],
    ["dim_cell", "lac_cell / site_id", "TEXT", "扇区键 / 站点编号（同坐标扇区归并）"],
    ["dim_cell", "lng / lat", "REAL", "站点坐标"],
    ["dim_cell", "district / aoi", "TEXT", "所属区县（市外兜底）/ 所属商圈（可为空）"],
    ["dim_hotspot", "name / radius_m", "TEXT / INT", "热点名称（西塔）/ 半径 500 米"],
    ["dim_hotspot", "lng / lat / 依据", "REAL / TEXT", "加权中心坐标 / 口径说明"],
    ["etl_log", "步骤 / 输入行数 / 输出行数", "TEXT / REAL / INT", "流水线每步的运行记录"],
    ["etl_log", "耗时(秒) / 运行时间 / 日期分区 / 批次", "—", "性能与追溯信息"],
    ["dq_check_result", "check_id / 维度 / 检查项", "TEXT", "稽核项标识与分类"],
    ["dq_check_result", "表字段 / 结果 / 状态", "TEXT", "检查对象、结论与判定（通过/警告/不通过）"],
    ["dq_check_result", "证据 / 处理决定", "TEXT", "判定依据与后续动作"],
]
add_table(doc, ["表", "字段", "类型", "说明"], dict_rows,
          [2.6, 3.6, 2.4, 5.6], size=9, caption="表 A-1  字段字典（节选）", first_col_left=True)

# ═══════════ 附录 B 发现清单 ═══════════
add_h(doc, "附录 B  发现清单（F1–F18）", 1)
add_body(doc, "D01–D05 探索过程中形成的关键发现及其影响，与本报告质量检查互为印证：")
findings = [
    ["F1", "97.3% 的记录在 10 月 3 日，10 月 1 日仅 54 条", "分析范围定为 10 月 3 日（DQ-01）"],
    ["F2", "凌晨 5 点最低仍有 14,369 条信令", "信令由网络自动产生，能判断过夜地"],
    ["F3", "23 点记录最多（33,769 条），不符合一般作息", "先查取数口径再下业务结论（F17 已解开）"],
    ["F4", "tmp0、tmp1 两列完全为空", "删除两列（DQ-02）"],
    ["F5", "关键字段最多缺 24 行", "删列；缺关键字段的行删除（DQ-03）"],
    ["F6", "8 条 IMSI 含 * ^ # 等掩码字符", "删除并反馈数据提供方（DQ-04）"],
    ["F7", "完全重复 2,568 行（0.48%）", "每组保留一条（DQ-06）"],
    ["F8", "前 15 位分组 15.6% 对应多个手机号，牵连 30.2% 用户", "主键改用完整 18 位 IMSI（DQ-08）"],
    ["F9", "清洗共剔除 3.2%，其中 2.7 个百分点是非 10 月 3 日记录", "明细表 515,931 行、用户 5,644 个"],
    ["F10", "基站表 49,954 行，6 行缺坐标；14,106 个站点，最常见 1 站点挂 3 扇区", "删缺坐标行；按坐标定义站点（DQ-10）"],
    ["F11", "信令与基站关联率超 99.99%，仅 8 个扇区关联不到坐标", "关联质量可靠（DQ-11）"],
    ["F12", "34% 的站点在沈阳市外，仅 1.8% 的信令发生在那里", "保留市外站点，区县标市外（DQ-12）"],
    ["F13", "v1 商圈边界有错误点、面积异常；json 版本为米制坐标", "采用 v2（DQ-13、DQ-14）"],
    ["F14", "97% 以上的用户当天到过和平区，远郊四区县不到 5%", "不是全市随机样本（DQ-15）"],
    ["F15", "热点在西塔，86% 的用户到过西塔 500 米以内", "热点写入 dim_hotspot"],
    ["F16", "西塔在场人数 17 点后猛增，41% 首次出现在 17–19 点", "样本是傍晚到访西塔的人群（DQ-15）"],
    ["F17", "23 点 37% 的信令发生在西塔 1 公里内（10 点为 16%）", "F3 解开：23 点峰值是西塔客流"],
    ["F18", "白天 71% 的人在和平区以外，19 点 38% 聚到西塔", "能讲这群人的一天，不能讲西塔白天有多少人"],
]
add_table(doc, ["编号", "发现", "影响 / 决定"], findings,
          [1.2, 8.2, 4.8], size=9, caption="表 B-1  发现清单（数据质量相关发现）", first_col_left=True)
doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run_font(p.add_run("—— 报告结束 ——"), cn=SERIF, size=10.5, color=FAINT)

# ═══════════ 目录（文档末尾生成，移动到文档控制页之后） ═══════════
toc_paras = []
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(10)
p.paragraph_format.page_break_before = True
run_font(p.add_run("目  录"), cn=SANS, size=18, bold=True, color=MAIN)
bottom_border(p, "1D6FA5")
toc_paras.append(p)
for level, text, bm in TOC_ENTRIES:
    if level > 2:
        continue                       # 目录只列章与节
    p = doc.add_paragraph()
    pf = p.paragraph_format
    # 固定行距 13pt：中文字体单倍行距含较大行高（约 1.5em），44 条条目必须固定行距才能一页放完
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(13)
    pf.space_before = Pt(0); pf.space_after = Pt(0)
    if level == 2:
        pf.left_indent = Cm(0.75)
    pf.tab_stops.add_tab_stop(Cm(14.6), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    run_font(p.add_run(text), cn=SANS if level == 1 else SERIF,
             size=11, bold=(level == 1), color=INK)
    p.add_run("\t")
    add_field(p, f"PAGEREF {bm} \\h")   # 页码自动域：与书签联动
    toc_paras.append(p)
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(6)
run_font(p.add_run("（页码为自动域：在 Word 中按 Ctrl+A 后 F9 即可刷新。）"), size=9, color=FAINT)
toc_paras.append(p)
anchor = PB_PARA
for tp in toc_paras:                    # 整体移动到文档控制页的分页段之后
    anchor._p.addnext(tp._p)
    anchor = tp

doc.save(str(OUT))
print(f"已生成：{OUT}")
