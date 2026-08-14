import os, json

_current_lang = "es"
_settings_path = None

_VOICES = {
    "es": "es-ES-ElviraNeural",
    "en": "en-US-AriaNeural",
}

_LANGUAGE_NAMES = {
    "es": "Español",
    "en": "English",
}

_SUPPORTED = tuple(_VOICES.keys())


def get_voice():
    """Devuelve el nombre de voz de Edge-TTS para el idioma activo"""
    """Returns the Edge-TTS voice name for the active language"""
    return _VOICES.get(_current_lang, _VOICES["es"])


def get_language_names():
    """Devuelve {codigo: nombre visible} de todos los idiomas soportados, en orden estable"""
    """Returns {code: display name} of all supported languages, in stable order"""
    return dict(_LANGUAGE_NAMES)


def init_language(config_dir):
    """Carga el idioma guardado (si existe) desde config_dir/settings.json. Llamar una vez al arrancar, antes de construir la interfaz"""
    """Loads the saved language (if any) from config_dir/settings.json. Call once at startup, before building the UI"""
    global _current_lang, _settings_path
    _settings_path = os.path.join(config_dir, "settings.json")
    if os.path.exists(_settings_path):
        try:
            with open(_settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lang = data.get("language", "es")
            if lang in _SUPPORTED:
                _current_lang = lang
        except Exception as e:
            print(f"Aviso: no se pudo leer la configuración de idioma: {e}")


def get_language():
    """Devuelve el idioma activo ('es' o 'en')"""
    """Returns the active language ('es' or 'en')"""
    return _current_lang


def has_saved_language(config_dir):
    """Indica si ya hay un idioma guardado en config_dir/settings.json, para decidir si hace falta preguntar"""
    """Indicates whether a language is already saved in config_dir/settings.json, to decide whether to ask"""
    return os.path.exists(os.path.join(config_dir, "settings.json"))


def set_language(lang):
    """Cambia el idioma activo y lo guarda en disco para la próxima vez"""
    """Changes the active language and saves it to disk for next time"""
    global _current_lang
    if lang not in _SUPPORTED:
        return
    _current_lang = lang
    if _settings_path:
        try:
            os.makedirs(os.path.dirname(_settings_path), exist_ok=True)
            with open(_settings_path, "w", encoding="utf-8") as f:
                json.dump({"language": lang}, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Aviso: no se pudo guardar la configuración de idioma: {e}")