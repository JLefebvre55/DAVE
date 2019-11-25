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


#Constants
DEBUG_MODE = True    #Print everything?

#Variable declarations and such
os.system('modprobe w1-gpio')    #1-W setup
os.system('modprobe w1-therm')    #^
wirefile = None        #Saves the 1-W file location so we only have to search for it once

#Oneliner functions
timems = lambda : int(time.time()*1000)
pumpHoldTime = lambda mL : mL*PUMP_FLOW_CONSTANT
getSensorValue = lambda button : button.value
separateReadDHT = lambda a, b, c : Adafruit_DHT.read_retry(a, b)[c]
formattedTime = lambda : time.strftime('%H:%M:%S', time.gmtime(12345))

#Function Definitions
def debug(status):    #Replaces print
    if(DEBUG_MODE):
        print("[DEBUG @"+formattedTime()+"] : "+status)

def formatState(state):
    if(type(state) is float):
        return "{:.2f}".format(state)
    else:
        return str(state)


def setup1Wire(directory, prefix):
    debug("Setting up 1-Wire device with prefix '"+str(prefix)+"'...")
    try:
        os.chdir(directory) #try open dir
    except:
        debug("Could not open directory '"+directory+"'")
        return
    else:
        for f in os.listdir(directory):  #find file that matches prefix
            if(f.startswith(prefix)):
                debug("Found '"+f+"'!")
                global wirefile
                wirefile = open(f+'/w1_slave', 'r') #open slave data file

def read1Wire(marker):
    debug("Reading 1-Wire device...")
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
            l = lines[1].strip()
            debug("Raw line: '"+l+"'")
            l = int(l[temp+2:])
            debug("Raw data: '"+str(l)+"'")
            return l/1000.0  #return C
        else:
            debug("No marker '"+marker+"' found in file!")
            return None
    debug("No 1-Wire bus file initialized!")
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
            debug("Done reading sensor '"+self.name+"'. State: "+formatState(str(temp)))
            return temp
        else:
            debug("Not ready to read '"+self.name+"', wait "+str(timems() - self.lastread)+"ms.")
        
#Handles environment variable adjustments in both the up (current < max) and down (current > max) directions, as well as when in range (usually turn things off)
class Actuator:
    def __init__(self, name, funcUp, funcDefault, funcDown, passEnvVar = (False, False, False), passActuator = (False, False, False), args0 = [], args1 = [], args2 = [], **kwargs):
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
        self.args0 = args0
        self.args1 = args1
        self.args2 = args2
        #Do default state
        self._actuate(1)
        #Will always be false unless set elsewhere
        self.busy = False
       #handle function rerouting based on envvar state
    def actuate(self, envvar):
        if(busy != True):
            index = 1
            if(envvar.current > max):
                index = 2
            elif(envvar.current < max):
                index = 0
            else:
                index = 1
            #handle arguments to pass based on actuator settings (defaults to no args)
            _actuate(index)
    def _actuate(self, index):
        msg = ""
        if(index == 0):
            temp = self.funcUp
            msg += "Actuated actuator '"+self.name+"' up, passing "
        elif(index == 1):
            temp = self.funcDefault
            msg += "Actuated actuator '"+self.name+"' to default, passing "
        else:
            temp = self.funcDown
            msg += "Actuated actuator '"+self.name+"' up, passing "
        #handle arguments to pass based on actuator settings (defaults to no args)
        args = self.args1 if index is 1 else self.args2 if index is 2 else self.args0
        if(self.passActuator[index]):
            args.append(self)
        if(self.passEnvVar[index]):
            args.append(envvar)
        msg+=str(len(args))+" arguments!"
        debug(msg)
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
    def update(self):
        temp = self.sensor.read()
        if(temp != None):
            self.current = temp

#Input Pins
waterlevel = Button(17)

#Output Pins
pumpWaterIn = DigitalOutputDevice(6)
airCooler = DigitalOutputDevice(22)
waterCooler = DigitalOutputDevice(27)

#Name, functions to call if {too low, in range, too high}
#OPTIONALLY: KEYWORDED boolean setting 3-tuples to pass envvar and/or the actuator object to the respective function (passActuator, passEnvVar)
#OPTIONALLY: KEYWORDED lists for additional arguments for each function (args0 to 2)
actuators=[ Actuator("Water In Pump", pumpWaterIn.on, pumpWaterIn.off, None),
            Actuator("Air Cooler", None, airCooler.off, airCooler.on),
            Actuator("Water Cooler", None, waterCooler.off, waterCooler.on)
]

#Name, Environment variable, Delay in ms, Read function and args
sensors = [ 
    Sensor("DHT-Humidity", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 0),
    Sensor("DHT-Temperature", 4000, separateReadDHT, Adafruit_DHT.DHT22, 13, 1),
    Sensor("Float Sensor", 500, getSensorValue, waterlevel),
    Sensor("Water Thermometer", 1000, read1Wire, 't=')
]

#Name, Homeostasis minimum and maximum values, sensor, actuator
environmentVariables = [ 
    EnvironmentVariable("Air Humidity", 80, 100, sensors[0], None),
    EnvironmentVariable("Air Temperature", 12, 15, sensors[1], actuators[1]),
    EnvironmentVariable("Water Level", 0, 1, sensors[2], actuators[0]),
    EnvironmentVariable("Water Temperature", 10, 12, sensors[3], actuators[2])
]
            
#Main
print("Setting up...")

setup1Wire('/sys/bus/w1/devices', '28-')

while True:
    print("Choose environment variable:")
    i = 1
    for envvar in environmentVariables:
        print(str(i)+": "+envvar.name)
        i+=1
    i = int(input())
    envvar = environmentVariables[i-1]
    print("What to do?\n1: Read variable\n2: Actuate")
    x = int(input())
    if(x==1):
        envvar.update()
        print("Attached sensor: "+envvar.sensor.name)
        print("State: "+str(envvar.current))
    elif (x == 2):
        if(envvar.actuator != None):
            print("Actuate as if variable was:\n1. Too low\n2. In range\n3. Too high")
            c = int(input())
            envvar.actuator._actuate(c-1)
        else:
            print("No attached actuator!")
        
