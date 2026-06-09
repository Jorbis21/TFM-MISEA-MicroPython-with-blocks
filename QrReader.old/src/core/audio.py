import pyttsx3
import threading

class GestorVoz:
    @staticmethod
    def _hablar_en_hilo(texto):
        motor_tts = pyttsx3.init()
        motor_tts.setProperty('rate', 150)
        motor_tts.say(texto)
        motor_tts.runAndWait()

    @classmethod
    def leer_texto(cls, texto):
        hilo_voz = threading.Thread(target=cls._hablar_en_hilo, args=(texto,), daemon=True)
        hilo_voz.start();