from microbit import *
import speech
import music
import random
from math import *
music.pitch(587, 100)
music.pitch(698, 100)
music.pitch(783, 100)

# --- Programa Principal ---
while True:
    if button_a.is_pressed() or button_b.is_pressed():
        print('TTS:' + str("pedo"))
        display.scroll("pedo")
    if pin_logo.is_touched():
        print('TTS:' + str(67))
        display.show(67)