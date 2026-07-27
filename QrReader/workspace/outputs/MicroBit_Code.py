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
    if button_b.is_pressed():
        print('TTS:' + str("socorrista"))
        display.scroll("socorrista")
    if button_a.is_pressed():
        print('TTS:' + str(224))
        display.show(224)
