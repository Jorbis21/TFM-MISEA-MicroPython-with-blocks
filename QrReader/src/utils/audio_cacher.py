import os
import sys
import re
import json
import asyncio
import hashlib
import edge_tts

# Misma ubicacion que el script original (2 niveles hasta la raiz del proyecto).
# Same location as the original script (2 levels up to the project root).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..'))

# Para poder hacer "from utils.strings import STRINGS" sin depender de con que
# directorio de trabajo se lance el script.
# So "from utils.strings import STRINGS" works regardless of the working
# directory the script is launched from.
SRC_DIR = os.path.join(BASE_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from utils.strings import STRINGS  # noqa: E402
from utils.language import _VOICES as VOICES  # noqa: E402

CACHE_ROOT = os.path.join(BASE_DIR, 'data', 'assets', 'audio_cache')

# Claves que no son frases pronunciables: vocabulario de reconocimiento por voz
# (nunca se leen en alto, solo se escuchan) o fragmentos usados para construir
# otras frases, no frases completas en si mismas.
# Keys that aren't speakable phrases: voice-recognition vocabulary (never read
# aloud, only listened for) or fragments used to build other phrases, not
# complete phrases on their own.
NON_SPEECH_KEYS = {
    "number_words", "number_prefix", "decimal_connectors",
    "junction_word", "image_word", "list_join_and",
    "gemini_prompt", "ollama_system_instructions",
}

PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")


def extract_static_phrases(lang_dict):
    """Recoge todas las frases fijas y pronunciables de un idioma: descarta claves de reconocimiento, fragmentos, y cualquier frase con {variables} porque esas se generan al vuelo"""
    """Collects all the fixed, speakable phrases of a language: discards recognition keys, fragments, and any phrase with {variables} since those are generated on the fly"""
    phrases = set()
    for key, value in lang_dict.items():
        if key.startswith("kw_") or key in NON_SPEECH_KEYS:
            continue
        if isinstance(value, str):
            if value and not PLACEHOLDER_RE.search(value):
                phrases.add(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item and not PLACEHOLDER_RE.search(item):
                    phrases.add(item)
    return phrases


async def cache_language(lang, voice):
    dest_dir = os.path.join(CACHE_ROOT, lang)
    os.makedirs(dest_dir, exist_ok=True)
    index_file = os.path.join(dest_dir, 'index.json')

    indice = {}
    if os.path.exists(index_file):
        with open(index_file, 'r', encoding='utf-8') as f:
            indice = json.load(f)

    frases = extract_static_phrases(STRINGS[lang])
    print(f"\n[{lang}] {len(frases)} frases estáticas encontradas en el catálogo de textos.")

    nuevas_descargas = 0
    for frase in frases:
        hash_frase = hashlib.md5(frase.encode('utf-8')).hexdigest()
        nombre_archivo = f"voz_{hash_frase}.mp3"
        ruta_archivo = os.path.join(dest_dir, nombre_archivo)

        if frase not in indice or not os.path.exists(ruta_archivo):
            print(f"[{lang}] Descargando audio para: '{frase}'...")
            try:
                communicate = edge_tts.Communicate(frase, voice, rate="+5%")
                await communicate.save(ruta_archivo)
                indice[frase] = nombre_archivo
                nuevas_descargas += 1
            except Exception as e:
                print(f"[{lang}] Error al descargar la frase '{frase}': {e}")

    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(indice, f, indent=4, ensure_ascii=False)

    print(f"[{lang}] Caché actualizada. {nuevas_descargas} audios nuevos. Total cacheadas: {len(indice)}.")


async def cache_all_languages():
    for lang, voice in VOICES.items():
        await cache_language(lang, voice)


if __name__ == "__main__":
    print("--- CONSTRUCTOR DE CACHÉ DE VOZ (ES + EN) ---")
    print("Ya no se rebusca el código fuente: se lee directamente el catálogo de utils/strings.py,")
    print("así que cualquier texto nuevo que uses con t(\"clave\") se cachea automáticamente.")
    asyncio.run(cache_all_languages())