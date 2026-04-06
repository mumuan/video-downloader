import json
import os
import tempfile
from pathlib import Path

import pytest

from src.parsers.session_manager import CurlSessionManager, VideoParseError


def test_session_manager_init():
    sm = CurlSessionManager()
    assert sm.cookie_dir.name == "cookies"
    assert sm.cookie_file.name == "cookies.json"


def test_is_cookie_valid_no_file(tmp_path):
    sm = CurlSessionManager()
    original = sm.cookie_file
    sm.cookie_file = tmp_path / "nonexistent.json"
    assert sm.is_cookie_valid() is False
    sm.cookie_file = original


def test_is_cookie_valid_expired_cookie(tmp_path):
    sm = CurlSessionManager()
    original = sm.cookie_file
    sm.cookie_file = tmp_path / "expired.json"
    expired_state = {
        "missav.com": [
            {
                "name": "cf_clearance",
                "value": "token",
                "expires": 1,  # 已过期
            }
        ]
    }
    with open(sm.cookie_file, "w") as f:
        json.dump(expired_state, f)
    assert sm.is_cookie_valid() is False
    sm.cookie_file = original


def test_is_cookie_valid_valid_cookie(tmp_path):
    sm = CurlSessionManager()
    original = sm.cookie_file
    sm.cookie_file = tmp_path / "valid.json"
    import time
    valid_state = {
        "missav.com": [
            {
                "name": "cf_clearance",
                "value": "token",
                "expires": time.time() + 86400,  # 24小时后过期
            }
        ]
    }
    with open(sm.cookie_file, "w") as f:
        json.dump(valid_state, f)
    assert sm.is_cookie_valid() is True
    sm.cookie_file = original
