import os
import asyncio
import threading
import uuid
import tempfile
import edge_tts
import pygame
import pyttsx3
import queue
import time

class GestorVoz:
    VOICE = "es-ES-ElviraNeural" 
    
    pygame.mixer.init()
    cola_tts = queue.Queue()
    worker_started = False

    @staticmethod
    def _iniciar_worker():
        if not GestorVoz.worker_started:
            GestorVoz.worker_started = True
            threading.Thread(target=GestorVoz._bucle_reproduccion, daemon=True).start()

    @staticmethod
    def _bucle_reproduccion():
        while True:
            texto, sin_internet = GestorVoz.cola_tts.get()
            GestorVoz._procesar_voz_bloqueante(texto, sin_internet)
            GestorVoz.cola_tts.task_done()

    @staticmethod
    def leer_texto(texto, sin_internet=False):
        GestorVoz._iniciar_worker()
        GestorVoz.cola_tts.put((texto, sin_internet))

    @staticmethod
    def _procesar_voz_bloqueante(texto, sin_internet=False):
        if not sin_internet:
            temp_dir = tempfile.gettempdir()
            archivo_mp3 = os.path.join(temp_dir, f"voz_{uuid.uuid4().hex}.mp3")

            try:
                asyncio.run(GestorVoz._descargar_audio(texto, archivo_mp3))
                pygame.mixer.music.load(archivo_mp3)
                pygame.mixer.music.play()
                
                # Esperar activamente a que termine la reproducción antes de soltar el hilo
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                    
                pygame.mixer.music.unload()
                try: os.remove(archivo_mp3) 
                except: pass
                return
                
            except Exception as e:
                print(f"Fallo Edge TTS, pasando a voz local. Motivo: {e}")
                
        try:
            motor_offline = pyttsx3.init()
            motor_offline.setProperty('rate', 160) 
            motor_offline.say(texto)
            motor_offline.runAndWait()
        except Exception as e_offline:
            print(f"Error crítico en el motor de voz offline: {e_offline}")

    @staticmethod
    async def _descargar_audio(texto, ruta):
        communicate = edge_tts.Communicate(texto, GestorVoz.VOICE, rate="+5%")
        await communicate.save(ruta)
    
    @staticmethod
    def leer_codigo_literal(ruta_codigo, sin_internet=False):
        try:
            with open(ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
            
            lineas = codigo.split('\n')

            leer = False
            lineas_visibles = []
            for linea in enumerate(lineas):
                if leer:
                    lineas_visibles.append(linea[1])
                if linea[1] == "# --- Programa Principal ---":
                    leer = True
                
            codigo_filtrado = "\n".join(lineas_visibles)

            codigo_limpio = codigo_filtrado.replace("*", "todo").replace("(", " paréntesis ").replace(")", "").replace(":", " dos puntos.")
            GestorVoz.leer_texto(f"El programa actual es el siguiente... {codigo_limpio}", sin_internet)
            
        except FileNotFoundError:
            GestorVoz.leer_texto("Aún no se ha generado ningún código.", sin_internet)

    @staticmethod
    def leer_qrs_pantalla(textos_qr_actuales):
        qrs_a_leer = list(textos_qr_actuales)
        
        if not qrs_a_leer:
            GestorVoz.leer_texto("No detecto ningún bloque en la mesa.")
        else:
            frases_posicionadas = []
            for indice, bloque in enumerate(qrs_a_leer):
                frases_posicionadas.append(f"posición {indice + 1}, {bloque}")
                
            texto_unido = ". ".join(frases_posicionadas).replace("_", " ")
            GestorVoz.leer_texto(f"Detectados {len(qrs_a_leer)} bloques. Leyendo de arriba a abajo... {texto_unido}.")