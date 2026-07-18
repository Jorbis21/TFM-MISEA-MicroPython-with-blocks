import os
import asyncio
import threading
import uuid
import tempfile
import edge_tts
import pygame
import pyttsx3

class GestorVoz:
    VOICE = "es-ES-ElviraNeural" 
    
    pygame.mixer.init()

    '''Metodo para lectura por voz'''
    @staticmethod
    def leer_texto(texto, sin_internet=False):
        hilo = threading.Thread(target=GestorVoz._procesar_voz, args=(texto, sin_internet,), daemon=True)
        hilo.start()

    '''Metodo para obtener y configurar la voz neural en caso de fallo usar el tts'''
    @staticmethod
    def _procesar_voz(texto, sin_internet=False):
        if not sin_internet:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()

            temp_dir = tempfile.gettempdir()
            archivo_mp3 = os.path.join(temp_dir, f"voz_{uuid.uuid4().hex}.mp3")

            try:
                asyncio.run(GestorVoz._descargar_audio(texto, archivo_mp3))
                pygame.mixer.music.load(archivo_mp3)
                pygame.mixer.music.play()
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

    '''Metodo para descargar la voz neural con el texto'''
    @staticmethod
    async def _descargar_audio(texto, ruta):
        communicate = edge_tts.Communicate(texto, GestorVoz.VOICE, rate="+5%")
        await communicate.save(ruta)
    
    '''Metodo para la lectura del codigo en caso de que fallen las IAs'''
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

    '''ESTE METODO HAY QUE CAMBIARLO PARA QUE DIGA EL NUMERO DE BLOQUES QUE HAY Y SU POSICION'''
    '''Metodo para leer los bloques que esta viendo la camara'''
    @staticmethod
    def leer_qrs_pantalla(textos_qr_actuales):
        qrs_a_leer = list(textos_qr_actuales)
        if not qrs_a_leer:
            GestorVoz.leer_texto("No detecto ningún bloque en la mesa.")
        else:
            texto_unido = ". ".join(qrs_a_leer).replace("_", " ")
            GestorVoz.leer_texto(f"Detectados {len(qrs_a_leer)} bloques. Leyendo de arriba a abajo: {texto_unido}")