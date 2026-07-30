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
while True:
    if pin_logo.is_touched():
        print('TTS:' + str(5))
        display.show(5)
    if button_a.is_pressed():
        print('TTS:' + str("chocolate"))
        display.scroll("chocolate")
