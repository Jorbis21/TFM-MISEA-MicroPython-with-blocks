from microbit import *
import speech
import music
import random
from math import *

# --- Sonido de inicialización ---
music.pitch(587, 100)
music.pitch(698, 100)
music.pitch(783, 100)
# --- Programa Principal ---

texto = "chocolate"
while True:
    if pin_logo.is_touched() and button_b.is_pressed():
        print('TTS:' + str(texto))
        display.scroll(texto)
    if button_a.is_pressed() or pin0.is_touched():
        print('TTS:' + str(8))
        display.show(8)
