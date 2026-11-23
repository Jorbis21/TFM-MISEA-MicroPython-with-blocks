# -*- mode: python ; coding: utf-8 -*-
#
# Para regenerar este .spec desde cero (p. ej. si cambian las dependencias):
#   pyi-makespec --name MicroPython_with_blocks --paths src src/main.py
# y volver a aplicar los cambios de este archivo (datas, console, icon).
#
# Para construir: pyinstaller MicroPython_with_blocks.spec (o mejor, build.bat, que ademas
# copia el .env automaticamente - ver mas abajo).
# Se ejecuta desde la raiz del proyecto (la carpeta que contiene src/ y data/).
#
# OJO: el .env (con la clave de Gemini) NO esta en los "datas" de abajo, y es
# a proposito - es una clave secreta, y no debe viajar embebida dentro de lo
# que empaqueta PyInstaller (_internal/), compartida con cualquiera que copie
# la carpeta. Tiene que copiarse a mano a dist/MicroPython_with_blocks/.env despues de cada
# build (build.bat ya lo hace por ti, tomandolo desde la raiz del proyecto).
# Lo mismo con el modelo de voz whisper_models/medium (build.bat lo descarga
# la primera vez y lo copia en cada build).

import os
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs

block_cipher = None

PROJECT_ROOT = os.path.abspath('.')
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')

# pyzbar se detecta solo en las pruebas que hice, pero si en Windows no
# incluyera su DLL nativa, esta linea la fuerza explicitamente sin hacer
# daño si ya estaba incluida por otra via.
pyzbar_binaries = collect_dynamic_libs('pyzbar')

a = Analysis(
    [os.path.join(SRC_DIR, 'main.py')],
    pathex=[SRC_DIR],
    binaries=pyzbar_binaries,
    datas=[
        # Iconos, estilos, y la cache de voz si ya la has generado con audio_cacher.py
        # (si existe, viaja con la app y no hace falta internet para las frases fijas)
        (os.path.join(PROJECT_ROOT, 'data', 'assets'), os.path.join('data', 'assets')),
        # OJO: el modelo de voz (whisper_models/) NO va aqui: son ~1.5 GB y
        # build.bat lo copia junto al .exe, igual que el .env.
        # NOTE: the voice model (whisper_models/) does NOT go here: it's ~1.5 GB
        # and build.bat copies it next to the .exe, same as the .env.
        # Los dos diccionarios de bloques. NO se incluye settings.json a proposito:
        # debe crearse en el primer arranque de cada copia, no venir fijado de fabrica.
        (os.path.join(PROJECT_ROOT, 'data', 'config', 'blocks_es.json'), os.path.join('data', 'config')),
        (os.path.join(PROJECT_ROOT, 'data', 'config', 'blocks_en.json'), os.path.join('data', 'config')),
        (os.path.join(PROJECT_ROOT, 'data', 'styles'), os.path.join('data', 'styles')),
    ],
    # uflash se importa de forma diferida dentro de una funcion
    # (code_manager.py, dentro de upload()), no al principio del archivo -
    # el analisis estatico de PyInstaller no lo detecta solo en ese caso,
    # comprobado empaquetando un caso minimo. Sin esto, "Enviar a MicroBit"
    # falla con "modulo uflash no encontrado" en el .exe aunque funcione
    # perfectamente ejecutando desde el codigo fuente.
    # uflash gets imported lazily inside a function (code_manager.py, inside
    # upload()), not at module top-level - PyInstaller's static analysis
    # doesn't detect it on its own in that case, confirmed by packaging a
    # minimal test case. Without this, "Send to MicroBit" fails with
    # "uflash module not found" in the .exe even though it works perfectly
    # running from source.
    # pygrabber (nombres de las camaras en Windows) tambien se importa de
    # forma diferida, dentro de camera_worker._get_device_names(): mismo
    # problema que uflash. Sin el, el .exe mostraria "Camara Principal/
    # Secundaria" en vez del nombre real y no elegiria la SVPRO sola.
    # pygrabber (camera names on Windows) is also imported lazily, inside
    # camera_worker._get_device_names(): same problem as uflash. Without it,
    # the .exe would show "Main/Secondary Camera" instead of the real name and
    # wouldn't pick the SVPRO on its own.
    # (pygrabber solo existe en Windows; en Linux/Mac los nombres se leen de otra forma)
    hiddenimports=['uflash'] + (['pygrabber', 'pygrabber.dshow_graph'] if sys.platform == 'win32' else []),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MicroPython_with_blocks',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # sin ventana de consola, es una app grafica
    icon=os.path.join(PROJECT_ROOT, 'data', 'assets', 'icons', 'once.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MicroPython_with_blocks',
)
