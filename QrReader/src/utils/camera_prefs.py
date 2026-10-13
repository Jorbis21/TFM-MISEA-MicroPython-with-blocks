import os, json

_prefs_path = None


def init_camera_prefs(config_dir):
    """Indica donde se guarda la camara preferida (config_dir/camera.json). Llamar una vez al arrancar"""
    """Sets where the preferred camera is stored (config_dir/camera.json). Call once at startup"""
    global _prefs_path
    _prefs_path = os.path.join(config_dir, "camera.json")


def get_saved_camera_name():
    """Devuelve el nombre de la ultima camara elegida por el usuario, o None"""
    """Returns the name of the last camera chosen by the user, or None"""
    if not _prefs_path or not os.path.exists(_prefs_path):
        return None
    try:
        with open(_prefs_path, "r", encoding="utf-8") as f:
            return json.load(f).get("camera_name")
    except Exception as e:
        print(f"Aviso: no se pudo leer la camara guardada: {e}")
        return None


def save_camera_name(name):
    """Guarda el nombre de la camara elegida para usarla directamente la proxima vez"""
    """Saves the name of the chosen camera to use it directly next time"""
    if not _prefs_path or not name:
        return
    try:
        os.makedirs(os.path.dirname(_prefs_path), exist_ok=True)
        with open(_prefs_path, "w", encoding="utf-8") as f:
            json.dump({"camera_name": name}, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Aviso: no se pudo guardar la camara elegida: {e}")
