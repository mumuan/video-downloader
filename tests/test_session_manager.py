import json
import os
import tempfile
from pathlib import Path

import pytest

from src.parsers.session_manager import SessionManager, VideoParseError


def test_session_manager_init():
    sm = SessionManager()
    assert sm.cookie_dir.name == "cookies"
    assert sm.state_file.name == "cloudflare_state.json"


def test_is_cookie_valid_no_file(tmp_path):
    sm = SessionManager()
    # 使用临时路径模拟无文件
    original = sm.state_file
    sm.state_file = tmp_path / "nonexistent.json"
    assert sm.is_cookie_valid() is False
    sm.state_file = original


def test_is_cookie_valid_expired_cookie(tmp_path):
    sm = SessionManager()
    original = sm.state_file
    sm.state_file = tmp_path / "expired.json"
    expired_state = {
        "cookies": [
            {
                "name": "cf_clearance",
                "value": "token",
                "expires": 1,  # 已过期
            }
        ]
    }
    with open(sm.state_file, "w") as f:
        json.dump(expired_state, f)
    assert sm.is_cookie_valid() is False
    sm.state_file = original


def test_is_cookie_valid_valid_cookie(tmp_path):
    sm = SessionManager()
    original = sm.state_file
    sm.state_file = tmp_path / "valid.json"
    import time
    valid_state = {
        "cookies": [
            {
                "name": "cf_clearance",
                "value": "token",
                "expires": time.time() + 86400,  # 24小时后过期
            }
        ]
    }
    with open(sm.state_file, "w") as f:
        json.dump(valid_state, f)
    assert sm.is_cookie_valid() is True
    sm.state_file = original
