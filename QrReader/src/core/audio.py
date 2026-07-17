import os
import asyncio
import threading
import uuid
import tempfile
import edge_tts
import pygame
import pyttsx3  # <-- LIBRERÍA OFFLINE PARA EL PLAN B

class GestorVoz:
    # Puedes cambiar esto por "es-ES-ElviraNeural" si prefieres voz femenina
    VOICE = "es-ES-AlvaroNeural" 
    
    # 1. Inicializamos el reproductor de audios de la nube (pygame sí es Thread-Safe)
    pygame.mixer.init()

    # ELIMINAMOS LA INICIALIZACIÓN GLOBAL DE PYTTSX3 AQUÍ

    @staticmethod
    def leer_texto(texto, sin_internet=False):
        """Lanza un hilo secundario para no congelar la interfaz."""
        hilo = threading.Thread(target=GestorVoz._procesar_voz, args=(texto, sin_internet,), daemon=True)
        hilo.start()

    @staticmethod
    def _procesar_voz(texto, sin_internet=False):
        if not sin_internet:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()

            temp_dir = tempfile.gettempdir()
            archivo_mp3 = os.path.join(temp_dir, f"voz_{uuid.uuid4().hex}.mp3")

            try:
                # INTENTO 1: NUBE (Edge TTS)
                asyncio.run(GestorVoz._descargar_audio(texto, archivo_mp3))
                pygame.mixer.music.load(archivo_mp3)
                pygame.mixer.music.play()
                return  # <--- IMPORTANTE: Salimos para que no se ejecute la voz offline
                
            except Exception as e:
                print(f"Fallo Edge TTS, pasando a voz local. Motivo: {e}")
                
        # INTENTO 2: FALLBACK LOCAL (pyttsx3)
        try:
            # SOLUCIÓN AL DEADLOCK: Inicializamos el motor estrictamente DENTRO del hilo
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

    # =========================================================
    # LECTURAS DE CONTEXTO (Lógica abstraída de la interfaz)
    # =========================================================
    
    @staticmethod
    def leer_codigo_literal(ruta_codigo):
        """Lee el código Python literal reemplazando símbolos problemáticos."""
        try:
            with open(ruta_codigo, "r", encoding="utf-8") as file:
                codigo = file.read()
            codigo_limpio = codigo.replace("*", "todo").replace("(", " paréntesis ").replace(")", "").replace(":", " dos puntos.")
            GestorVoz.leer_texto(f"El programa actual es el siguiente... {codigo_limpio}")
        except FileNotFoundError:
            GestorVoz.leer_texto("Aún no se ha generado ningún código.")

    @staticmethod
    def leer_qrs_pantalla(textos_qr_actuales):
        """Lee de forma ordenada los QRs detectados por la cámara."""
        qrs_a_leer = list(textos_qr_actuales)
        if not qrs_a_leer:
            GestorVoz.leer_texto("No detecto ningún bloque en la mesa.")
        else:
            texto_unido = ". ".join(qrs_a_leer).replace("_", " ")
            GestorVoz.leer_texto(f"Detectados {len(qrs_a_leer)} bloques. Leyendo de arriba a abajo: {texto_unido}")