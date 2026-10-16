#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_config.py
# @Path       : signal-insight/test/unit/test_config.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: config 的单元测试：项目根定位与口径常量。
"""config 的单元测试：项目根定位与口径常量。"""
import pytest

from signal_insight import config


def test_find_project_root_hits_marker():
    root = config.find_project_root()
    assert (root / config.WORKSPACE_MARKER).exists()


def test_project_root_contains_package_and_data():
    assert (config.PROJECT_ROOT / "src" / "signal_insight").is_dir()
    assert (config.PROJECT_ROOT / "data").is_dir()


def test_find_project_root_missing_marker_raises(tmp_path, monkeypatch):
    """把 config.__file__ 指到没有 marker 的目录深处：逐级向上都找不到就报错。"""
    monkeypatch.setattr(config, "__file__", str(tmp_path / "deep" / "fake_config.py"))
    with pytest.raises(FileNotFoundError, match="signal.workspace"):
        config.find_project_root()


def test_constants():
    assert config.UTC_OFFSET_HOURS == 8
    assert config.ANALYSIS_DAY == "2018-10-03"
    assert config.DB_PATH == config.DATA_DIR / "signal.db"
    assert config.WORKSPACE_MARKER == "signal.workspace"
