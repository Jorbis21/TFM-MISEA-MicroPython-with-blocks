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
# la carpeta. Tiene que copiarse a mano a dist/QrReader/.env despues de cada
# build (build.bat ya lo hace por ti, tomandolo desde la raiz del proyecto).

import os
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
        # Los dos diccionarios de bloques. NO se incluye settings.json a proposito:
        # debe crearse en el primer arranque de cada copia, no venir fijado de fabrica.
        (os.path.join(PROJECT_ROOT, 'data', 'config', 'blocks_es.json'), os.path.join('data', 'config')),
        (os.path.join(PROJECT_ROOT, 'data', 'config', 'blocks_en.json'), os.path.join('data', 'config')),
        (os.path.join(PROJECT_ROOT, 'data', 'styles'), os.path.join('data', 'styles')),
    ],
    hiddenimports=[],
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
    name='MicroPython with blocks',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # sin ventana de consola, es una app grafica
    # icon=os.path.join(PROJECT_ROOT, 'data', 'assets', 'icons', 'once.ico'),
    # ^ descomenta esta linea cuando tengas el .ico (necesita ser .ico, no .png)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MicroPython with blocks',
)
