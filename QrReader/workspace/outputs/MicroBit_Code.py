from microbit import *

while True:
	if button_a.is_pressed():
		display.show(39)
	if button_b.is_pressed():
		display.show(Image.BUTTERFLY)
