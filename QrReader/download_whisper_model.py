"""
    Descarga el modelo Whisper "medium" (formato faster-whisper) a una carpeta,
    para incluirlo en el portable y que la aplicacion no tenga que descargar
    nada al arrancar (equipos sin internet o detras del proxy del centro).

    Downloads the Whisper "medium" model (faster-whisper format) to a folder,
    to include it in the portable so the app doesn't have to download anything
    at startup (computers without internet or behind the school's proxy).

    Uso / Usage:
        pip install huggingface_hub
        python download_whisper_model.py <carpeta_del_portable>

    build.bat lo ejecuta solo, desde la raiz del proyecto / build.bat runs it
    on its own, from the project root:
        python download_whisper_model.py .
    -> crea / creates whisper_models/medium/{model.bin, config.json, ...}
    y build.bat lo copia a dist/MicroPython_with_blocks/whisper_models/medium/

    La aplicacion busca esa carpeta junto al ejecutable (y tambien entre los
    recursos empaquetados), igual que la carpeta portable de Ollama.
    The app looks for that folder next to the executable (and also among the
    bundled resources), same as the portable Ollama folder.
"""
import os
import sys

from huggingface_hub import snapshot_download

REPO_ID = "Systran/faster-whisper-medium"
FILES = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]


def main():
    target_root = sys.argv[1] if len(sys.argv) > 1 else "."
    dest = os.path.join(target_root, "whisper_models", "medium")
    os.makedirs(dest, exist_ok=True)

    model_bin = os.path.join(dest, "model.bin")
    if os.path.isfile(model_bin) and os.path.getsize(model_bin) > 1_000_000_000:
        print(f"El modelo ya esta descargado en {dest}, no se vuelve a descargar.")
        return

    print(f"Descargando {REPO_ID} en {dest} ...")
    snapshot_download(repo_id=REPO_ID, local_dir=dest, allow_patterns=FILES)

    if not os.path.isfile(model_bin):
        sys.exit("ERROR: no se ha descargado model.bin")

    # La cache interna de huggingface_hub no hace falta en el portable
    # huggingface_hub's internal cache isn't needed in the portable
    hf_cache = os.path.join(dest, ".cache")
    if os.path.isdir(hf_cache):
        import shutil
        shutil.rmtree(hf_cache, ignore_errors=True)

    size_mb = sum(os.path.getsize(os.path.join(dest, f)) for f in os.listdir(dest)) / 1e6
    print(f"Modelo listo ({size_mb:.0f} MB): {dest}")


if __name__ == "__main__":
    main()
