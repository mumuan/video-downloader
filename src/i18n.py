import json
import os

_translations = {}
_current_lang = "en"

def init_i18n():
    """Initialize i18n with English as default."""
    global _current_lang
    _current_lang = "en"
    _load_translations()

def _load_translations():
    """Load translation JSON files."""
    global _translations
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for lang in ["en", "zh"]:
        path = os.path.join(base_dir, "translations", f"{lang}.json")
        with open(path, encoding="utf-8") as f:
            _translations[lang] = json.load(f)

def _(key: str) -> str:
    """Translate a string key to the current language."""
    return _translations.get(_current_lang, {}).get(key, key)

def set_language(lang: str):
    """Manually set language (for testing)."""
    global _current_lang
    if lang in _translations:
        _current_lang = lang