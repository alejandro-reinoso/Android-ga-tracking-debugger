import os
import json


'''
 i18n - Translation Handling
'''
TRANSLATIONS = {}
CURRENT_LANG = "en"  # Default fallback language


def load_translations():
    """Loads translations from the 'locales.json' file."""
    global TRANSLATIONS
    path_locales = "locales.json"

    if not os.path.exists(path_locales):
        print("'locales.json' not found; hardcoded literals will be used.")
        TRANSLATIONS = {}
        return

    with open(path_locales, "r", encoding="utf-8") as f:
        TRANSLATIONS = json.load(f)


def set_language(lang):
    """Changes the current language (e.g., 'es', 'en', etc.)."""
    global CURRENT_LANG
    CURRENT_LANG = lang


def _(key):
    """
    Returns the translated text based on the key and current language.
    If not found, returns the key itself as fallback.
    """
    return TRANSLATIONS.get(CURRENT_LANG, {}).get(key, key)