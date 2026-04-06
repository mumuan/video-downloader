import json
import os

from PyQt6.QtCore import QLocale

_translations = {}
_current_lang = "en"

def init_i18n():
    """Initialize i18n with system language detection."""
    global _current_lang
    system_lang = QLocale.system().bcp47Name().split("-")[0]
    _current_lang = system_lang if system_lang in ["en", "zh"] else "en"
    _load_translations()

def _load_translations():
    """Load translation JSON files."""
    global _translations
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for lang in ["en", "zh"]:
        path = os.path.join(base_dir, "translations", f"{lang}.json")
        try:
            with open(path, encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Fallback to empty dict, _() will return key as-is
            _translations[lang] = {}

def _ensure_initialized():
    """Ensure translations are loaded before using set_language."""
    if not _translations:
        init_i18n()

def _(key: str) -> str:
    """Translate a string key to the current language."""
    if not _translations:
        _ensure_initialized()
    return _translations.get(_current_lang, {}).get(key, key)

def set_language(lang: str):
    """Manually set language."""
    _ensure_initialized()
    global _current_lang
    if lang in _translations:
        _current_lang = lang
    else:
        # Fall back to English silently
        _current_lang = "en"

def get_language() -> str:
    """Get current language code."""
    return _current_lang