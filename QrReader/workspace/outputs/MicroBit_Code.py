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
    if button_a.is_pressed():
        display.show(Image.ALL_CLOCKS)
    if button_b.is_pressed():
        audio.play(Sound.GIGGLE)
    elif pin_logo.is_touched():
        display.scroll(temperature())
