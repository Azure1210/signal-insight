"""从生成的 PDF 里量出每个目录标题落在第几页，写 .pagemap.json 供二次生成用。"""

import json
import re
from pathlib import Path

import fitz
from docx import Document

ROOT = Path(__file__).resolve().parent
DOCX = ROOT / "沈阳移动信令数据分析报告_分析版_20261019.docx"
PDF = ROOT / ".tmp_report.pdf"
OUT = ROOT / ".pagemap.json"


def norm(s):
    return re.sub(r"\s+", "", s)


doc = Document(str(DOCX))
entries = []
for p in doc.paragraphs:
    if p.style.name in ("toc 1", "toc 2"):
        text = p.text.split("\t")[0].strip()
        if text:
            entries.append(text)

pdf = fitz.open(str(PDF))
pages = [norm(pg.get_text()) for pg in pdf]

cursor = 2  # 0-based：跳过封面与目录页
mapping = {}
for text in entries:
    key = norm(text)
    found = None
    for i in range(cursor, len(pages)):
        if key and key in pages[i]:
            found = i
            break
    if found is None:
        print("NOT FOUND:", text)
        continue
    mapping[key] = found + 1
    cursor = found

OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"entries {len(entries)}, mapped {len(mapping)}")
for k, v in mapping.items():
    print(f"  {v:>3}  {k}")
