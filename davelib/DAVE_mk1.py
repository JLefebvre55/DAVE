#Outlines default specs for DAVE_mk1

from DAVE_Lib import *

#Input Pins
waterlevel = Button(17)

#Output Pins
pumpWaterIn = DigitalOutputDevice(6)
airCooler = DigitalOutputDevice(22)
waterCooler = DigitalOutputDevice(27)
growLights = DigitalOutputDevice(25)

wirefilesrc = find1Wire('/sys/bus/w1/devices', '28-')


__standardEVs__ = [
    EnvironmentVariable("Air Humidity (%H)", 80, 100, 90,
                        Sensor("DHT-Humidity", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 0), 
                        None),
    EnvironmentVariable("Air Temperature (C)", 12, 15, 14,
                        Sensor("DHT-Temperature", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 1), 
                        Actuator("Air Cooler", None, airCooler.off, airCooler.on)),
    EnvironmentVariable("Water Level (1Hi, 0Lo)", 0, 1, 1,
                        Sensor("Float Sensor", 500, getSensorValue, waterlevel), 
                        Actuator("Water In Pump", (lambda a : (pumpWaterIn.on(), holdActuator(a, 60))), pumpWaterIn.off, None, passActuator = (True, False, False))),
    EnvironmentVariable("Water Temperature (C)", 10, 14, 13.2,
                        Sensor("Water Thermometer", 1000, read1Wire, wirefilesrc, 't='), 
                        Actuator("Water Pump/Cooler", None, waterCooler.off, waterCooler.on)),
    EnvironmentVariable("Light", 0, 1, None,
                        None,
                        Actuator("Grow Lights", growLights.on, growLights.off, None))
]