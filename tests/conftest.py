import pytest
from src.i18n import init_i18n, set_language

# Initialize i18n with English for all tests to ensure consistent behavior
init_i18n()
set_language("en")
