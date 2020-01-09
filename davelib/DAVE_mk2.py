#Outlines default specs for DAVE_mk1

from DAVE_Lib import *

#Input Pins
waterlevel = Button(17)

#Output Pins
growLights = DigitalOutputDevice(6)
fans = DigitalOutputDevice(22)

#1-Wire setup
os.system('modprobe w1-gpio')    #1-W setup
os.system('modprobe w1-therm')    #^
wirefilesrc = find1Wire('/sys/bus/w1/devices', '28-')

#!!! DB COLUMN ORDER AND TYPE MUST MATCH ENVIRONMENT VARIABLE ORDER AND TYPE !!!
#...excluding id and timestamp

db = {"name" : "davedb", 
              "user" : "dave", 
              "password" : "password",
              "host" : "localhost",
              'delta': 15,
              "columns": ["id INT PRIMARY KEY AUTO_INCREMENT", #index
                          "timestamp TIMESTAMP NOT NULL", #timestamp
                          "airhum DECIMAL(4,2) NOT NULL",
                          "airtemp DECIMAL(4,2) NOT NULL",
                          "waterlevel_ishigh boolean NOT NULL",
                          "watertemp DECIMAL(4,2) NOT NULL",
                          "ph DECIMAL(4,2) NOT NULL",
                          "electric_conductivity DECIMAL(6,2) NOT NULL"]
              }

ard = {
    "serial" : '/dev/ttyACM0',
    "baud" : 9600
}

#constants
delay = 1

#ENSURE EVS ARE IN SAME ORDER AS DATABASE
evs = [
    EnvironmentVariable("Air Humidity (%H)", 60, 80, 70,
                        Sensor("DHT-Humidity", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 0), 
                        Actuator),
                        #Actuator("Cirulation Fans", None, fans.off, fans.on)),
    EnvironmentVariable.noActuator("Air Temperature (C)", 12, 15, 13.5,
                        Sensor("DHT-Temperature", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 1), 
                        2),
                        #Actuator("Air Cooler", None, airCooler.off, airCooler.on)),
    EnvironmentVariable.noActuator("Water Level (1Hi, 0Lo)", 0, 1, 1,
                        Sensor("Float Sensor", 500, getSensorValue, waterlevel), 
                        0),
                        #Actuator("Water In Pump", (lambda a : (pumpWaterIn.on(), a.hold(30))), pumpWaterIn.off, None, passActuator = (True, False, False))),
    EnvironmentVariable.noActuator("Water Temperature (C)", 9, 12, 10,
                        Sensor("Water Thermometer", 1000, read1Wire, wirefilesrc, 't='),
                        2),
                        #Actuator("Water Pump/Cooler", None, waterCooler.off, waterCooler.on)),
    EnvironmentVariable.noActuator("pH", 5.5, 6.0, 6.5,
                        Sensor("Arduino-pH Sensor", 4000, readArduinoSensor, "pH"),
                        0.3),
    EnvironmentVariable.noActuator("Eletrical Conductivity", 1000, 1250, 1500,
                        Sensor("Arduino-EC Sensor", 4000, readArduinoSensor, "EC"),
                        250),
]

#A schedule is a list of "index"-"delta" pairs controlling an actuator. 0-up, 1-def, 2-down
acts = [
    Actuator.scheduled("Lights", growLights.on, growLights.off, None, 
                       [
                           {"index" : 2, "timestamp" : timestamp(8)},
                           {"index" : 0, "timestamp" : timestamp(16)}
                        ]
                       )
    ]



cam = {
    "path" : '/home/pi/Desktop/dave_photos/',    #mUST end in slash
    "light" : Actuators[0],
    "resolution": (1280, 720),
    'delta' : 1200
}