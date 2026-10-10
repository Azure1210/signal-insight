#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : config.py
# @Path       : signal-insight/src/signal_insight/config.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-10 14:53:18
# @Version    : v1.1.0
# @Description: 
# @ChangeLog:
#   2026-10-10 14:53:18 | Matri | v1.0.0 | 初始化创建
#   2026-10-10 16:30:00 | Matri | v1.1.0 | 新增主题配置 THEME / THEME_DIR
import os
from pathlib import Path

# 项目根的标记文件：根目录里只要有这个文件，就能锁定项目根，
# 不再依赖 config.py 本身所在的层级（parents 数量）。
WORKSPACE_MARKER = "signal.workspace"


def find_project_root(marker: str = WORKSPACE_MARKER) -> Path:
    """从 config.py 所在目录逐级向上查找含 marker 的目录，作为项目根路径。

    这样即使 config.py 以后移动到包内更深的层级，
    也能靠根目录里的 signal.workspace 标记文件找到正确的项目根。
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).exists():
            return parent
    raise FileNotFoundError(
        f"未找到项目根标记文件 {marker!r}，请确认它存在于项目根目录"
    )


PROJECT_ROOT = find_project_root()

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "signal.db"  # 探索库
# 检查库，前一天没做完可以从这里恢复
CHECKPOINT_DB = DATA_DIR / "checkpoints.db"

IMAGE_DIR = PROJECT_ROOT / "image"

# 可视化主题：内置 default(原配色) / academic(学术规范) / business(商业规范)。
# 环境变量 SIGNAL_THEME 可临时覆盖，例如 SIGNAL_THEME=academic python run.py
THEME = os.environ.get("SIGNAL_THEME", "default")
# 自定义主题目录：放进去的 *.toml 会在导入 viz 时自动注册（目录不存在则忽略）
THEME_DIR = PROJECT_ROOT / "themes"

# 口径常量：
UTC_OFFSET_HOURS = 8
ANALYSIS_DAY = "2018-10-03"
SOURCE_NOTE = "数据来源：沈阳移动信令样本(脱敏，2018年国庆)"
AUTHOR = "AzureKite 1210"
