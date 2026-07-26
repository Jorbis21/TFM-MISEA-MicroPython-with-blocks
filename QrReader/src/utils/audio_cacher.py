import os
import ast
import json
import asyncio
import hashlib
import edge_tts

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CACHE_DIR = os.path.join(BASE_DIR, 'data', 'assets', 'audio_cache')
INDEX_FILE = os.path.join(CACHE_DIR, 'index.json')
VOICE = "es-ES-ElviraNeural"

DIRECTORIOS_IGNORADOS = {'.git', 'venv', 'env', '__pycache__', 'data', 'workspace'}

class BuscadorFrasesVoz(ast.NodeVisitor):
    def __init__(self):
        self.frases = set()

    def visit_Call(self, node):
        # 1. Llamadas directas a funciones de voz con texto literal
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['leer_texto', 'leer_texto_interrumpiendo', 'bucle_confirmacion_voz']:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    self.frases.add(node.args[0].value)
        
        # 2. Capturar automáticamente los títulos de todos los QPushButton("...") de la interfaz
        if isinstance(node.func, ast.Name) and node.func.id == 'QPushButton':
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                self.frases.add(node.args[0].value)
                
        self.generic_visit(node)

    def visit_Assign(self, node):
        # 3. Capturar cadenas asignadas a la variable 'texto' (como las descripciones de iconos: "Rotar cámara", etc.)
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'texto':
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    self.frases.add(node.value.value)
        self.generic_visit(node)

def extraer_frases_del_codigo():
    buscador = BuscadorFrasesVoz()
    archivos_procesados = 0

    for raiz, carpetas, archivos in os.walk(BASE_DIR):
        carpetas[:] = [c for c in carpetas if c not in DIRECTORIOS_IGNORADOS]
        
        for archivo in archivos:
            if archivo.endswith('.py'):
                ruta_completa = os.path.join(raiz, archivo)
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    try:
                        arbol = ast.parse(f.read(), filename=archivo)
                        buscador.visit(arbol)
                        archivos_procesados += 1
                    except SyntaxError:
                        print(f"Error de sintaxis al leer {archivo}, omitiendo...")

    print(f"Se han analizado {archivos_procesados} archivos .py en todo el proyecto.")
    return buscador.frases

async def descargar_frases(frases):
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    indice = {}
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            indice = json.load(f)

    nuevas_descargas = 0
    print("\nComprobando caché de audio para botones y sistema...")
    
    for frase in frases:
        hash_frase = hashlib.md5(frase.encode('utf-8')).hexdigest()
        nombre_archivo = f"voz_{hash_frase}.mp3"
        ruta_archivo = os.path.join(CACHE_DIR, nombre_archivo)

        if frase not in indice or not os.path.exists(ruta_archivo):
            print(f"Descargando audio para: '{frase}'...")
            try:
                communicate = edge_tts.Communicate(frase, VOICE, rate="+5%")
                await communicate.save(ruta_archivo)
                indice[frase] = nombre_archivo
                nuevas_descargas += 1
            except Exception as e:
                print(f"Error al descargar la frase '{frase}': {e}")

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(indice, f, indent=4, ensure_ascii=False)
        
    print(f"\n¡Caché actualizada! Se han descargado {nuevas_descargas} audios nuevos.")
    print(f"Total de frases estáticas cacheadas: {len(indice)}")

if __name__ == "__main__":
    print("--- CONSTRUCTOR DE CACHÉ DE VOZ INTELIGENTE ---")
    frases_encontradas = extraer_frases_del_codigo()
    print(f"Se han encontrado {len(frases_encontradas)} frases totales (incluyendo botones).")
    asyncio.run(descargar_frases(frases_encontradas))