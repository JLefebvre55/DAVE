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
from picamera import PiCamera
import mysql.connector as mariadb

#Constants
__debugLevel__ = 1    #0-Errors, 1-Read values and Actions, 2-Device setup and read start/ends, 3-All other
__delay__ = 0.1     #Time in s between serial sensor reads
__setup__ = False
__database__ = None

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
formattedTime = lambda : str(datetime.datetime.now().time()).split('.')[0]

#Function Definitions
def debug(status, level):    #Replaces print
    if(level <= __debugLevel__):
        print("[DEBUG !"+str(level)+" @"+formattedTime()+"] : "+status)

def formatState(state):
    if(type(state) is float):
        return "{:.2f}".format(state)
    else:
        return str(state)

def find1Wire(directory, prefix):
    debug("Setting up 1-Wire device with prefix '"+str(prefix)+"'...", 2)
    try:
        os.chdir(directory) #try open dir
    except:
        debug("Could not open directory '"+directory+"'", 0)
        return
    else:
        for f in os.listdir(directory):  #find file that matches prefix
            if(f.startswith(prefix)):
                debug("Found '"+f+"'!", 3)
                return f+'/w1_slave' #save path

def read1Wire(wirefile, marker):
    debug("Reading 1-Wire device...", 2)
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
                debug("Raw line: '"+l+"'", 2)
                l = int(l[temp+2:])
                debug("Raw data: '"+str(l)+"'", 2)
                file.close()
                return l/1000.0  #return C
        except:
            debug("No marker '"+marker+"' found in file!", 0)
            return None
    debug("No 1-Wire bus file initialized!", 0)
    return None    

def holdActuator(actuator, time):
    thread.start_new_thread(_holdActuator, (actuator, time))
    
def _holdActuator(actuator, time):
    actuator.busy = True
    sleep(time)
    actuator.busy = False

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
            debug("Reading sensor '"+self.name+"'...", 2)
            temp = self.func(*self.args)
            self.lastread = timems()
            debug("Sensor '"+self.name+"' raw state: "+formatState(str(temp)), 2)
            return temp
        else:
            debug("Not ready to read '"+self.name+"', wait "+str(timems() - self.lastread)+"ms.", 3)
        
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
        self.args = (args0, args1, args2)
        #Do default state
        self._actuate(1)
        self.trajectory = 1
        #Will always be false unless set elsewhere
        self.busy = False
       #handle function rerouting based on envvar state
    def actuate(self, envvar):
        if(self.busy is True):
            debug("'"+self.name+"' is busy!", 3)
        elif(envvar.optimal != None):
            index = self.trajectory
            if(envvar.current >= envvar.max):
                debug("'"+envvar.name+"' is too high! "+str(envvar.current)+" >= "+str(envvar.max), 2)
                index = 2
            elif(envvar.current <= envvar.min):
                debug("'"+envvar.name+"' is too low! "+str(envvar.current)+" <= "+str(envvar.min), 2)
                index = 0
            elif((self.trajectory == 2 and envvar.current <= envvar.optimal) or (self.trajectory == 0 and envvar.current >= envvar.optimal)):
                print("'"+envvar.name+"' has reached optimal. "+str(envvar.current)+" ~ "+str(envvar.optimal)+". T:"+str(self.trajectory))
                index = 1
            #handle arguments to pass based on actuator settings (defaults to no args)
            if(index != self.trajectory):
                self.trajectory = index
                self._actuate(index)
            else:
                debug(self.name+" already has trajectory "+str(self.trajectory)+"!", 3)
            
    def _actuate(self, index):
        msg = ""
        if(index == 0):
            f = self.funcUp
            msg += "Actuated actuator '"+self.name+"' up, passing "
        elif(index == 2):
            f = self.funcDown
            msg += "Actuated actuator '"+self.name+"' down, passing "
        else:
            f = self.funcDefault
            msg += "Actuated actuator '"+self.name+"' to default, passing "
        #handle arguments to pass based on actuator settings (defaults to no args)
        
        args = []
        
        for a in self.args[index]:
            args.append(a)
        
        if(self.passActuator[index]):
            debug("Appended actuator to actuation args", 3)
            args.append(self)
        if(self.passEnvVar[index]):
            debug("Appended envvar to actuation args", 3)
            args.append(envvar)
        msg+=str(len(args))+" arguments!"
        debug(msg, 1)
        f(*args)

#Manages the state of environment variables as reported by the sensors relative to their minimum and maximum homeostatic optima
class EnvironmentVariable:
    def __init__(self, name, min, max, optimal, sensor, actuator):
        self.name = name
        self.min = min
        self.sensor = sensor
        self.actuator = actuator
        self.current = optimal
        self.max = max
        self.optimal = optimal
        self.update()
    def update(self):
        if(self.sensor != None):
            temp = self.sensor.read()
            if(temp != None):
                self.current = temp
            else:
                debug("'"+self.sensor.name+"' read as None, is this supposed to happen?", 0)

def setup(EVs = [], dbInfo = None, debug = 0, delay = 0.1, **kwargs):
    print("Performing first time DAVE setup...")
    global __debugLevel__, __EVs__, __delay__, __setup__, __database__
    __debugLevel__ = debug
    __delay__ = delay
    __EVs__ = EVs
    if(dbInfo != None):
        __database__ = mariadb.connect(user=dbInfo.user, password=dbInfo.password, database=dbInfo.name)
    __setup__ = True
    
def run():
    if(__setup__):
        ("Welcome to the DAVE Homeostasis Engine!") 
        while True:
            for ev in __EVs__:
                ev.update()    #Sense
                if(ev.actuator != None):
                    ev.actuator.actuate(ev) #Plan, Act
                if(ev.sensor != None):
                    print(ev.name+": "+formatState(ev.current))
                sleep(__delay__)
    else:
        print("[ERR]: Setup has not yet been performed!")
            
def interface():
    if(__setup__):
        exit = False
        dbcursor = __database__.cursor()
        print("Welcome to the DAVE manual interface!\n")
        while True:
            print("What to do?\n1: Read variable\n2: Actuate\n3: Read from MySQL database\n4: Write to MySQL database\n5: Quit")
            x = int(input())
            if(x == 5):
                break
            if(x==4):
                dbcursor.execute("")
            if(x == 3):
                dbcursor.execute("SELECT * FROM sensordata")
                print(dbcursor)
            print("Choose an environment variable:")
            i = 1
            for envvar in __EVs__:
                print(str(i)+": "+envvar.name)
                i+=1
            i = int(input())
            envvar = __EVs__[i-1]
            if(x==1):
                if(envvar.sensor != None):
                    envvar.update()
                    print("Attached sensor: "+envvar.sensor.name)
                    print("State: "+str(envvar.current))
                else:
                    print("No attached sensor!")
            elif (x == 2):
                if(envvar.actuator != None):
                    if(envvar.actuator.busy):
                        print("Actuator is busy.")
                    else:
                        print("Actuate as if variable was:\n1. Too low (up)\n2. In range (default)\n3. Too high (down)")
                        c = int(input())
                        envvar.actuator._actuate(c-1)
                else:
                    print("No attached actuator!")
        print("Goodbye!")
        sleep(1)
    else:
        print("[ERR]: Setup has not yet been performed!")
        
