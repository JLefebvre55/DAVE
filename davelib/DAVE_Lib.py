#Library of all cross-DAVE functionality
    #Finding and reading 1-Wire bus
    #Debug console
    #DAVE instantiation and runtime
    #All major classes (see below)

from gpiozero import LED, Button, DigitalOutputDevice
from time import sleep, time
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

#Variable declarations and such
os.system('modprobe w1-gpio')    #1-W setup
os.system('modprobe w1-therm')    #^

#EMPTY LISTS - To be filled at declaration
__EVs__ = []
__Actuators__ = []
__arduinoData__ = {}    #Arduino parsed JSON data
__databaseManager__ = None
__cameraManager__ = None
__arduino__ = None  #arduino serial port

#Oneliner functions
timems = lambda : int(time()*1000)
pumpHoldTime = lambda mL : mL*PUMP_FLOW_CONSTANT
getSensorValue = lambda button : button.value
separateReadDHT = lambda a, b, c : Adafruit_DHT.read_retry(a, b)[c]

#Function Definitions
def debug(status, level):    #Replaces print
    if(level == 0):
        print("[!-ERROR-! @"+str(datetime.datetime.now().time()).split('.')[0]+"] : "+status)
    elif(level <= __debugLevel__):
        print("[DEBUG !"+str(level)+" @"+str(datetime.datetime.now().time()).split('.')[0]+"] : "+status)

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
    debug("Holding actuator '"+actuator.name+"' at state '"+str(actuator.trajectory)+"' for "+str(time)+"s.", 3)
    thread.start_new_thread(_holdActuator, (actuator, time))
    
def _holdActuator(actuator, time):
    actuator.busy = True
    sleep(time)
    actuator.busy = False

def readArduinoSensor(name):
    updateArduino()
    debug("Fetching Arduino sensor '"+name+"' from data table.", 3)
    if name in __arduinoData__:
        return __arduinoData__[name]
    else:
        debug("Attempted to fetch unknown Arduino sensor '"+name+"' from data table.", 0)
    
def updateArduino():
    debug("Updating Arduino data table", 2)
    #Read serial until valid data occurs
    while True:
        #Successful read?
        try:
            line = __arduino__.readline()[:-1]
        except Exception as e:
            debug("Serial error: '"+str(e)+"'", 0)
            sleep(1)
            continue
        debug("Read line from serial: '"+line+"'", 3)
        #Successful parse?
        try:
            data = json.loads(line)
        except ValueError:
            debug("Incomplete JSON from arduino!", 0)
            sleep(1)
            continue
        if(type(data) is list):
            for sensor in data:
                if "state" not in sensor.keys() or "name" not in sensor.keys():
                    debug("Missing data in JSON from arduino!")
                    sleep(1)
                    continue
            debug("Sucessfully parsed valid JSON: "+str(data), 3)
            for sensor in data:
                __arduinoData__[sensor["name"]] = sensor["state"]
        else:
            debug("Non-list data from arduino!", 0)

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

class DBManager:
    def __init__(self, settings):
        self.settings = settings
        self.delta = settings['delta']
        try:
            debug("Creating database manager...", 3)
            self.database = mariadb.connect(host = settings["host"], user=settings["user"], password=settings["password"], database=settings["name"])
        except mariadb.Error as error:
            print("[ERR]: Error creating database manager; '{}'".format(error))
        self.cursor = self.database.cursor()
        self.setupTables()
        debug("Database manager created!", 3)
        self.lastUpdate = time()
    def setupTables(self):
        debug("Setting up DB tables. Columns:", 2)
        command = "CREATE TABLE IF NOT EXISTS sensordata("
        for col in self.settings["columns"][:-1]:
            debug("- "+col, 2)
            command+=col
            command+=","
        command+=self.settings["columns"][-1]
        debug("- "+self.settings["columns"][-1], 2)
        command+=");"   #terminator
        self.execute(command)
        debug("DB tables set up successfully.", 2)
    def sendSensorData(self, evs):
        debug("Collecting all current sensor data...", 3)
        command = "INSERT INTO sensordata ("
        for col in self.settings["columns"][1:-1]:
            command+=col.split(" ")[0]+","
        command+=(self.settings["columns"][-1]).split(" ")[0]
        command += ") VALUES (\""+str(datetime.datetime.now()).split(".")[0]+"\","
        for sensor in evs[:-1]:
            command+= str(sensor.current)+","
            debug("- "+str(sensor.name)+" ("+formatState(sensor.current)+")", 3)
        command += str(evs[-1].current)+");"
        debug("- "+str(evs[-1].name)+" ("+formatState(evs[-1].current)+")", 3)
        debug("Sending all current sensor data to database!", 1)
        self.execute(command)
        self.lastUpdate = time()
    def execute(self, command):
        debug("Executing MySQL commmand: "+command, 3)
        try:
            self.cursor.execute(command)
        except mariadb.Error as e:
            debug("MySQL Error: '"+str(e)+"'", 0)

class CameraManager:
    def __init__(self, settings):
        debug("Creating camera manager...", 1)
        self.light = settings['light']
        self.camera = PiCamera()
        self.camera.resolution = settings["resolution"]
        if settings["path"][-1] is not '/':
            settings["path"].append('/')
        self.path = settings["path"]
        self.delta = settings['delta']
        self.lastCapture = time()
    def capture(self):
        if(self.light != None):
            self.light._actuate(0)
            self._capture()
            self.light._actuate(1)
        else:
            self._capture()
        self.lastCapture = time()
    def _capture(self):
        debug("Capturing an image!", 1)
        self.camera.start_preview()
        sleep(3)
        self.camera.capture(self.formatPath())
        self.camera.stop_preview()
    def formatPath(self):
        return '{0}dave_{1}.jpg'.format(self.path, str(datetime.datetime.now()).split(".")[0].replace(' ','_'))

def setup(evs = [], actuators = [], debug = 0, delay = 0.1, arduino = None, db = None, cam = None, **kwargs):
    print("Performing first time DAVE setup...")
    global __debugLevel__, __EVs__, __Actuators__, __delay__, __setup__, __databaseManager__, __arduino__, __cameraManager__
    __debugLevel__ = debug
    __delay__ = delay
    __EVs__ = evs
    __Actuators__ = actuators
    if(arduino != None):
        __arduino__ = serial.Serial(arduino["serial"], arduino["baud"])
        updateArduino()
    if(db!=None):
        __databaseManager__ = DBManager(db)
    if(cam != None):
        __cameraManager__ = CameraManager(cam)
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
            if(time() - __databaseManager__.lastUpdate > __databaseManager__.delta):
                __databaseManager__.sendSensorData(__EVs__)
            if(time() - __cameraManager__.lastCapture > __cameraManager__.delta):
                __cameraManager__.capture()
                    
    else:
        print("[ERR]: Setup has not yet been performed!")
            
def interface():
    if(__setup__):
        print("Welcome to the DAVE manual interface!\n")
        while True:
            x=-1
            while x < 0 or x > 6:
                print("What to do?\n1: Read variable\n2: Actuate\n3: Read latest from MySQL database\n4: Write current to MySQL database\n5: Take a photo\n6: Quit")
                x = int(input())
            
            if(x == 1):
                print("Choose an environment variable:")
                i=-1
                while i < 0 or i > len(__EVs__):
                    i = 1
                    for sensor in __EVs__:
                        print(str(i)+": "+sensor.name)
                        i+=1
                    i = int(input())
                __EVs__[i-1].update()
                print("Attached sensor: "+__EVs__[i-1].sensor.name)
                print("State: "+str(__EVs__[i-1].current))
                    
            elif(x == 2):
                print("Choose an actuator:")
                #Create compound list of EVs with actuators as well as standalone actuators
                newList = __Actuators__[:]
                for ev in __EVs__:
                    if ev.actuator != None:
                        newList.append(ev.actuator)
                i = -1
                while i < 0 or i > len(newList):
                    i = 1
                    for actuator in newList:
                        print(str(i)+": "+actuator.name)
                        i+=1
                    i = int(input())
                actuator = newList[i-1]
                if(actuator.busy):
                    print("Actuator is busy.")
                else:
                    print("Actuate trajectory:\n1. Up\n2. Default\n3. Down")
                    c = int(input())
                    actuator._actuate(c-1)
            elif(x == 6):
                break
            elif(x == 5):
                __cameraManager__.capture()
                print("Captured!")
            elif(x==4):
                __databaseManager__.sendSensorData(__EVs__)
            elif(x == 3):
                try:
                    __databaseManager__.cursor.execute("SELECT * FROM sensordata")
                    result = __databaseManager__.cursor.fetchall()[-1]
                    print(result)
                except mariadb.Error as error:
                    print("[ERR]: {}".format(error))
                except IndexError as error:
                    print("[ERR]: Table has no rows!")
        print("Goodbye!")
        sleep(1)
    else:
        print("[ERR]: Setup has not yet been performed!")
        
