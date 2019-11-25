#Library of all cross-DAVE functionality
    #Finding and reading 1-Wire bus
    #Debug console
    #DAVE instantiation and runtime
    #All major classes (see below)

from gpiozero import LED, Button, DigitalOutputDevice
from time import sleep, time as Time
import datetime
import Adafruit_DHT
import os
import thread
import serial
import json

#Constants
__doDebug__ = False    #Print everything?
__delay__ = 0.1     #Time in s between serial sensor reads

#Variable declarations and such
os.system('modprobe w1-gpio')    #1-W setup
os.system('modprobe w1-therm')    #^

#EMPTY LISTS - To be filled at declaration
__EVs__ = []

#Oneliner functions
timems = lambda : int(Time()*1000)
pumpHoldTime = lambda mL : mL*PUMP_FLOW_CONSTANT
getSensorValue = lambda button : button.value
separateReadDHT = lambda a, b, c : Adafruit_DHT.read_retry(a, b)[c]
floatSensorInvert = lambda sensor : 1-getSensorValue(sensor)
formattedTime = lambda : datetime.datetime.now().time().split('.')[0]

#Function Definitions
def debug(status):    #Replaces print
    if(__doDebug__):
        print("[DEBUG @"+formattedTime()+"] : "+status)

def formatState(state):
    if(type(state) is float):
        return "{:.2f}".format(state)
    else:
        return str(state)

def find1Wire(directory, prefix):
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
                return f+'/w1_slave' #save path

def read1Wire(wirefile, marker):
    debug("Reading 1-Wire device...")
    if(wirefile != None):
        file = open(wirefile, 'r')
        lines = file.readlines()
                #for line in lines:
                    #print(line)
                #while lines[0].strip[-3:] != 'YES': #wait for YES signal
                    #time.sleep(0.2)
                    # = x.readlines()
        try:
            temp = lines[1].find(marker)  #find temp data
                #print(temp)
            if(temp != -1):
                l = lines[1].strip()
                debug("Raw line: '"+l+"'")
                l = int(l[temp+2:])
                debug("Raw data: '"+str(l)+"'")
                file.close()
                return l/1000.0  #return C
        except:
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
        self.current = 1
        #Will always be false unless set elsewhere
        self.busy = False
       #handle function rerouting based on envvar state
    def actuate(self, envvar):
        if(self.busy != True):
            index = 1
            if(envvar.current >= envvar.max):
                debug("'"+envvar.name+"' is too high! "+str(envvar.current)+" >= "+str(envvar.max))
                index = 2
            elif(envvar.current <= envvar.min):
                debug("'"+envvar.name+"' is too low! "+str(envvar.current)+" <= "+str(envvar.min))
                index = 0
            else:
                debug("'"+envvar.name+"' is in range. "+str(envvar.min)+" < "+str(envvar.current)+" < "+str(envvar.max))
                index = 1
            #handle arguments to pass based on actuator settings (defaults to no args)
            if(index != self.current):
                self._actuate(index)
        else:
            debug("'"+self.name+"' is busy!")
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
            msg += "Actuated actuator '"+self.name+"' down, passing "
        #handle arguments to pass based on actuator settings (defaults to no args)
        args = self.args1 if index is 1 else self.args2 if index is 2 else self.args0
        if(self.passActuator[index]):
            args.append(self)
        if(self.passEnvVar[index]):
            args.append(envvar)
        msg+=str(len(args))+" arguments!"
        debug(msg)
        temp(*args)
        self.current = index

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

def DAVE(EVs = [], debug = False, delay = 0.1, **kwargs):
    global __doDebug__, __EVs__, __delay__
    __doDebug__ = debug
    __delay__ = delay
    __EVs__ = EVs
    
def run():
    while True:
        for ev in __EVs__:
            ev.update()    #Sense
            if(ev.actuator != None):
                ev.actuator.actuate(ev) #Plan, Act
            print(ev.name+": "+formatState(ev.current))
            sleep(__delay__)