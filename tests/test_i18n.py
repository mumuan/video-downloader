import pytest
from src.i18n import _, init_i18n, set_language, get_language

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

def test_get_language_returns_current():
    init_i18n()
    set_language("en")
    assert get_language() == "en"
    set_language("zh")
    assert get_language() == "zh"

def test_set_language_before_init_initializes_and_sets():
    # This should work without calling init_i18n first
    set_language("zh")
    assert get_language() == "zh"
    assert _("Download") == "下载"

def test_set_language_fallback_to_english_for_unknown():
    init_i18n()
    set_language("fr")  # unsupported language
    assert get_language() == "en"