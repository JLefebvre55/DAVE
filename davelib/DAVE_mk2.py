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

#!!! DB COLUMN ORDER AND TYPE MUST MATCH ENVIRONMENT VARIABLE ORDER AND TYPE !!!
#...excluding id and timestamp

__dbInfo__ = {"name" : "davedb", 
              "user" : "dave", 
              "password" : "password",
              "host" : "localhost",
              "columns": ["id INT PRIMARY KEY AUTO_INCREMENT", #index
                          "timestamp TIMESTAMP NOT NULL", #timestamp
                          "airhum DECIMAL(4,2) NOT NULL",
                          "airtemp DECIMAL(4,2) NOT NULL",
                          "waterlevel_ishigh boolean NOT NULL",
                          "watertemp DECIMAL(4,2) NOT NULL",
                          "ph DECIMAL(4,2) NOT NULL",
                          "electric_conductivity DECIMAL(6,2) NOT NULL"]
              }

__arduinoInfo__ = {
    "serial" : '/dev/ttyACM0',
    "baud" : 9600
}

#constants
__hasCamera__ = True
__hasArduino__ = True
__delay__ = 1


#ENSURE EVS ARE IN SAME ORDER AS DATABASE
__EVs__ = [
    EnvironmentVariable("Air Humidity (%H)", 80, 100, 90,
                        Sensor("DHT-Humidity", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 0), 
                        None),
    EnvironmentVariable("Air Temperature (C)", 12, 15, 14,
                        Sensor("DHT-Temperature", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 1), 
                        Actuator("Air Cooler", None, airCooler.off, airCooler.on)),
    EnvironmentVariable("Water Level (1Hi, 0Lo)", 0, 1, 1,
                        Sensor("Float Sensor", 500, getSensorValue, waterlevel), 
                        Actuator("Water In Pump", (lambda a : (pumpWaterIn.on(), holdActuator(a, 30))), pumpWaterIn.off, None, passActuator = (True, False, False))),
    EnvironmentVariable("Water Temperature (C)", 10, 14, 13.2,
                        Sensor("Water Thermometer", 1000, read1Wire, wirefilesrc, 't='), 
                        Actuator("Water Pump/Cooler", None, waterCooler.off, waterCooler.on)),
    EnvironmentVariable("pH", 6.0, 7.0, 6.5,
                        Sensor("Arduino-pH Sensor", 4000, readArduinoSensor, "pH"),
                        None),
    EnvironmentVariable("Eletrical Conductivity", 1000, 1250, 1500,
                        Sensor("Arduino-EC Sensor", 4000, readArduinoSensor, "EC"),
                        None),
    EnvironmentVariable("Light", 0, 1, None,
                        None,
                        Actuator("Grow Lights", growLights.on, growLights.off, None))
]