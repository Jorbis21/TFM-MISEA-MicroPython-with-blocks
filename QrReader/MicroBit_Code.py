from microbit import *

while True:
	if button_a.is_pressed():
		display.scroll('Hello!')
