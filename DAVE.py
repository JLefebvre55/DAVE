#TODO
#Add actuators to arduino sensors
#Fix possible bug - multiple arduino-dependent background threads?
#Define pump control time-volume relationship
#Define pH volume given constants function
#replace most prints with debugs

from gpiozero import LED, Button, DigitalOutputDevice
import time
from time import sleep
import Adafruit_DHT
import os
import thread
import serial
import json
from inspect import signature

#Variable declarations and such
DEBUG_MODE = False    #Print everything?
os.system('modprobe w1-gpio')    #1-W setup
os.system('modprobe w1-therm')    #^
wirefile = None        #Saves the 1-W file location so we only have to search for it once
arduinoData = {}    #Arduino parsed JSON data
arduino = serial.Serial('/dev/ttyACM0', 9600)   #arduino serial port

#Oneliner functions
timems = lambda : int(time.time()*1000)
getSensorValue = lambda button : button.value
separateReadDHT = lambda a, b, c : Adafruit_DHT.read_retry(a, b)[c]
formattedTime = lambda : time.strftime('%H:%M:%S', time.gmtime(12345))

#Function Definitions
def debug(status):    #Replaces print
    if(DEBUG_MODE):
        print("[DEBUG @"+formattedTime()+"] : "+status)

def readArduinoSensor(name):
    if name in arduinoData:
        return arduinoData[name]

def formatState(state):
    if(type(state) is float):
        return "{:.2f}".format(state)
    else:
        return str(state)
    
#def pumpControl(pump, amount):
    #thread.start_new_thread(pumpcontrol, (pump, amount))

#def _pumpControl(pump, amount):

def getPHAdjustAmount(current, constant, target):
    currentH = 10**(-current)
    targetH = 10**(-target)
    deltaH = targetH - currentH

def setup1Wire(directory, prefix):
    try:
        os.chdir(directory) #try open dir
    except:
        return
    else:
        for f in os.listdir(directory):  #find file that matches prefix
            if(f.startswith(prefix)):
                wirefile = open(f+'/w1_slave', 'r') #open slave data file

def read1Wire(marker):
    if(wirefile != None):
        lines = wirefile.readlines()
                #for line in lines:
                    #print(line)
                #while lines[0].strip[-3:] != 'YES': #wait for YES signal
                    #time.sleep(0.2)
                    # = x.readlines()
        temp = lines[1].find(marker)  #find temp data
                #print(temp)
        if(temp != -1):
            return int(lines[1].strip()[temp+2:])/1000.0  #return C
    return None

#MAJOR CLASSES - Env Var holds 1 sensor and 1 actuator.

#Handles GPIO-EnvVar relations, as well as delays, read functionality, etc.
#Effectively a wrapper for the read function
class Sensor:
    def __init__(self, name, delay, func, *args):
        self.name = name
        self.delay = delay  #Time in ms between reads
        self.lastread = 0 #last time read (intialized for buffer time)
        self.func = func
        self.args = args
        
    def read(self):
        if(timems() - self.lastread >= self.delay):
            debug("Reading sensor '"+self.name+"'...")
            temp = self.func(*self.args)
            self.lastread = timems()
            debug("Done reading sensor '"+self.name+"'! State: "+str(self.state))
            return temp
        
#Handles environment variable adjustments in both the up (current < max) and down (current > max) directions, as well as when in range (usually turn things off)
class Actuator:
    def __init__(self, name, funcUp, funcDefault, funcDown, passEnvVar = (false, false, false), passActuator = (false, false, false), args0 = [], args1 = [], args2 = [], **kwargs):
        self.name = name
        
        if(funcUp == None):            #Default all outside-range operations to default (provides redundancy)
            funcUp = funcDefault
        self.funcUp = funcUp
        if(funcDown == None):
            funcDown = funcDefault
        self.funcDown = funcDown
        self.funcDefault = funcDefault
        #Arg settings
        self.passEnvVar = passEnvVar
        self.passActuator = passActuator
        #Will always be false unless set elsewhere
        self.busy = False
       #handle function rerouting based on envvar state
    def actuate(self, envvar):
        if(busy != True):
            index = -1
            msg = ""

            temp = None
            if(envvar.current > max):
                temp = funcDown
                index = 2
                msg = "Actuated actuator '"+self.name+"' down, passing "
            elif(envvar.current < max):
                temp = funcUp
                index = 0
                msg = "Actuated actuator '"+self.name+"' up, passing "
            else:
                temp = funcDefault
                index = 1
                msg = "Actuated actuator '"+self.name+"' back to default state, passing "
        #handle arguments to pass based on actuator settings (defaults to no args)
        args = args1 if index is 1 else args2 if index is 2 else args0
        if(passActuator[index]):
            args.append(self)
        if(passEnvVar[index]):
            args.append(envvar)
        #msg+=str(args.len())+" arguments!"
        temp(*args)

#Manages the state of environment variables as reported by the sensors relative to their minimum and maximum homeostatic optima
class EnvironmentVariable:
    def __init__(self, name, min, max, sensor, actuator):
        self.name = name
        self.min = min
        self.sensor = sensor
        self.actuator = actuator
        self.current = sensor.read()
        self.max = max

#Input Pins
waterlevel = Button(17)

#Output Pins
pumpWaterIn = DigitalOutputDevice(6)
airCooler = DigitalOutputDevice(22)
waterCooler = DigitalOutputDevice(27)
pumpPHUp = DigitalOutputDevice()
pumpPHDown = DigitalOutputDevice()
pumpNutrients = DigitalOutputDevice()


#Name, functions to call if {too low, in range, too high}
#OPTIONALLY: KEYWORDED boolean setting 3-tuples to pass envvar and/or the actuator object to the respective function (passActuator, passEnvVar)
#OPTIONALLY: KEYWORDED lists for additional arguments for each function (args0 to 2)
actuators=[ Actuator("Water In Pump", pumpWaterIn.on, pumpWaterIn.off, None),
            Actuator("Air Cooler", None, airCooler.off, airCooler.on),
            Actuator("Water Cooler", None, waterCooler.off, waterCooler.on),
            Actuator("pH Pumps", pumpControl, lambda: (pumpPHUp.off(), pumpPHDown.off()), pumpControl, passActuator = (true, false, true), passEnvVar = (true, false, true), args0 = [pumpPHUp], args2 = [pumpPHDown]),
            ]

#Name, Environment variable, Delay in ms, Read function and args
sensors = [ 
    Sensor("DHT-Humidity", 4000, None, separateReadDHT, Adafruit_DHT.DHT22, 13, 0),
    Sensor("DHT-Temperature", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 1),
    Sensor("Float Sensor", 500, getSensorValue, waterlevel),
    Sensor("Water Thermometer", 1000, read1Wire, 't='),
    Sensor("Arduino-pH Probe", 1000, readArduinoSensor, 'pH'),
    Sensor("Arduino-Conductivity Probe", 1000, readArduinoSensor, 'Conductivity')
]

#Name, Homeostasis minimum and maximum values
environmentVariables = [ 
    EnvironmentVariable("Air Humidity", 60, 80),
    EnvironmentVariable("Air Temperature", 12, 15),
    EnvironmentVariable("Water Level", 0, 1),
    EnvironmentVariable("Water Temperature", 10, 12),
    EnvironmentVariable("pH", 6.1, 6.5),
    EnvironmentVariable("Conductivity", 1300, 1600)
]
            
#Main
print("Setting up...")

setup1Wire('/sys/bus/w1/devices', '28-')


while True:
    updateArduino()
    for envvar in environmentVariables:
        envvar.sensor.read()    #Sense
        envvar.actuator.actuate(envvar) #plan, act
