import pytest
from src.i18n import _, init_i18n, set_language

def test_translate_returns_english_by_default():
    init_i18n()
    set_language("en")
    assert _("Download") == "Download"

def test_translate_returns_chinese_when_set():
    init_i18n()
    set_language("zh")
    assert _("Download") == "下载"

def test_translate_unknown_key_returns_key():
    init_i18n()
    set_language("en")
    assert _("nonexistent_key") == "nonexistent_key"