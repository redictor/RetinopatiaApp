import json
import os

_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "jsons",
    "language_settings.json"
)
_LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

SUPPORTED_LANGUAGES = ["ru", "en", "zh"]
DEFAULT_LANGUAGE = "en"

_current_lang = DEFAULT_LANGUAGE
_translations = {}


def _load_settings() -> dict:
    if not os.path.exists(_SETTINGS_PATH):
        return {}
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_settings(data: dict) -> None:
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect_system_language() -> str:
    mapping = {"ru": "ru", "en": "en", "zh": "zh"}

    if os.name == "nt":
        try:
            import ctypes
            windll = ctypes.windll.kernel32
            lang_id = windll.GetUserDefaultUILanguage()
            primary_lang = lang_id & 0x3FF
            windows_lang_map = {0x19: "ru", 0x09: "en", 0x04: "zh"}
            if primary_lang in windows_lang_map:
                return windows_lang_map[primary_lang]
        except Exception:
            pass

    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if val:
            prefix = val.split(".")[0].split("_")[0].lower()
            if prefix in mapping:
                return mapping[prefix]

    try:
        from PyQt5 import QtCore
        locale_name = QtCore.QLocale.system().name()
        lang_prefix = locale_name.split("_")[0].lower()
        if lang_prefix in mapping:
            return mapping[lang_prefix]
    except Exception:
        pass

    return DEFAULT_LANGUAGE


def get_saved_language() -> str | None:
    settings = _load_settings()
    lang = settings.get("language")
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return None


def is_first_launch() -> bool:
    settings = _load_settings()
    return not settings.get("language_selected", False)


def set_language(lang_code: str) -> None:
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = DEFAULT_LANGUAGE
    settings = _load_settings()
    settings["language"] = lang_code
    settings["language_selected"] = True
    _save_settings(settings)
    load_language(lang_code)


def load_language(lang_code: str) -> None:
    global _current_lang, _translations
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = DEFAULT_LANGUAGE

    path = os.path.join(_LOCALES_DIR, f"{lang_code}.json")
    with open(path, "r", encoding="utf-8") as f:
        _translations = json.load(f)
    _current_lang = lang_code


def get_current_language() -> str:
    return _current_lang


def t(key: str, **kwargs) -> str:
    parts = key.split(".")
    node = _translations
    for p in parts:
        if isinstance(node, dict) and p in node:
            node = node[p]
        else:
            return key

    if isinstance(node, str) and kwargs:
        try:
            return node.format(**kwargs)
        except (KeyError, IndexError):
            return node
    return node if isinstance(node, str) else key

def _flat_translations(node=None, prefix=""):
    """Yield stable keys for already translated static widget texts."""
    if node is None:
        node = _translations
    for name, value in node.items():
        key = f"{prefix}.{name}" if prefix else name
        if isinstance(value, dict):
            yield from _flat_translations(value, key)
        elif isinstance(value, str) and value and "{" not in value:
            yield key, value


def capture_widget_texts(root, preferred_section=None):
    """Call BEFORE switching language. Doesn't mutate visible text."""
    from PyQt5 import QtWidgets, QtCore
    lookup = {}
    for key, value in _flat_translations():
        lookup.setdefault(value, key)
    for widget in root.findChildren(QtWidgets.QWidget):
        if isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            key = lookup.get(widget.text())
            if key:
                widget.setProperty("_app_i18n_text", key)
            tooltip_key = lookup.get(widget.toolTip())
            if tooltip_key:
                widget.setProperty("_app_i18n_tooltip", tooltip_key)
        if isinstance(widget, QtWidgets.QComboBox):
            for index in range(widget.count()):
                key = lookup.get(widget.itemText(index))
                if key:
                    widget.setItemData(index, key, QtCore.Qt.UserRole + 42)


def retranslate_widget_texts(root):
    """Call AFTER switching language. Doesn't recreate any screen."""
    from PyQt5 import QtWidgets, QtCore
    for widget in root.findChildren(QtWidgets.QWidget):
        if isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            key = widget.property("_app_i18n_text")
            if isinstance(key, str):
                widget.setText(t(key))
            tooltip_key = widget.property("_app_i18n_tooltip")
            if isinstance(tooltip_key, str):
                widget.setToolTip(t(tooltip_key))
        if isinstance(widget, QtWidgets.QComboBox):
            for index in range(widget.count()):
                key = widget.itemData(index, QtCore.Qt.UserRole + 42)
                if isinstance(key, str):
                    widget.setItemText(index, t(key))
    root.update()