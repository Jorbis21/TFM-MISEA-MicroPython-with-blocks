import os
import asyncio
import threading
import uuid
import tempfile
import edge_tts
import pygame
import pyttsx3  # <-- LIBRERÍA OFFLINE PARA EL PLAN B

class GestorVoz:
    # Puedes cambiar esto por "es-ES-AlvaroNeural" si prefieres voz masculina
    VOICE = "es-ES-ElviraNeural" 
    
    # 1. Inicializamos el reproductor de audios de la nube
    pygame.mixer.init()

    # 2. Inicializamos el motor de voz local (Plan B)
    motor_offline = pyttsx3.init()
    # Opcional: Le subimos un poco la velocidad a la voz de Windows para que no sea tan lenta
    motor_offline.setProperty('rate', 160) 

    @staticmethod
    def leer_texto(texto, sin_internet):
        """
        Lanza un hilo secundario para no congelar la interfaz gráfica 
        mientras se gestionan las voces.
        """
        hilo = threading.Thread(target=GestorVoz._procesar_voz, args=(texto,sin_internet,), daemon=True)
        hilo.start()

    @staticmethod
    def _procesar_voz(texto, sin_internet):
        if not sin_internet:
            # Si hay un audio de Edge TTS sonando, lo callamos
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()

            temp_dir = tempfile.gettempdir()
            archivo_mp3 = os.path.join(temp_dir, f"voz_{uuid.uuid4().hex}.mp3")

            try:
                # ==============================================================
                # INTENTO 1: NUBE (Edge TTS)
                # ==============================================================
                # Si no hay internet, esto lanzará un error y saltará al except
                asyncio.run(GestorVoz._descargar_audio(texto, archivo_mp3))
                
                pygame.mixer.music.load(archivo_mp3)
                pygame.mixer.music.play()
                
            except Exception as e:
                pass
            # ==============================================================
            # INTENTO 2: FALLBACK LOCAL (pyttsx3)
            # ==============================================================
            print(f"Sin internet para voz neuronal. Usando voz local. Motivo: {e}")
            
        try:
            # Usamos la voz nativa de tu Windows (normalmente Helena o Sabina)
            GestorVoz.motor_offline.say(texto)
            GestorVoz.motor_offline.runAndWait()
        except Exception as e_offline:
            print(f"Error crítico en el motor de voz offline: {e_offline}")

    @staticmethod
    async def _descargar_audio(texto, ruta):
        communicate = edge_tts.Communicate(texto, GestorVoz.VOICE, rate="+5%")
        await communicate.save(ruta)