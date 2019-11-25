from time import sleep
from gpiozero import DigitalOutputDevice

PIN = 6

pump = DigitalOutputDevice(PIN)

sleep(0.1)
pump.on()
sleep(1)
pump.off()