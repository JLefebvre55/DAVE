#General rules
#Do delay calculation inside function being called. Let IT decide if enough time has passed (see: sensor, actutator (busy), database, camera)
#Start all delays at delta, EXCEPT sensor reads. When DAVE boots, I want all sensor-actuator interactions to start immediately. Give the database and camera some time though.
#format instead of +str(x)+
#use words "is, not, in"

#--IMPORTS--#
from gpiozero import LED, Button, DigitalOutputDevice
from time import sleep, time
from datetime import datetime, time as timestamp
import Adafruit_DHT
import os
import thread
import serial
import json
from picamera import PiCamera
import mysql.connector as mariadb

secondsSinceMidnight = lambda : (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
timems = lambda : int(time()*1000)
getSensorValue = lambda button : button.value
separateReadDHT = lambda a, b, c : Adafruit_DHT.read_retry(a, b)[c]

#--FUNCTION DEFINITIONS--#
#pass
def debug(status, level):    #Replaces print. 0-Error, 1-Stuff you want to see all the time, 2-Genuine debugging, 3-The seventh circle of Hell
    if(level == 0):
        print("[!-ERROR-! @"+str(datetime.datetime.now().time()).split('.')[0]+"] : "+status)
    elif(level <= __debugLevel__):
        print("[DEBUG !"+str(level)+" @"+str(datetime.datetime.now().time()).split('.')[0]+"] : "+status)

#pass
def formatState(state): #Turns raw state data into eyeball-friendly strings
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
                    debug("Missing data in JSON from arduino!", 0)
                    sleep(1)
                    continue
            debug("Sucessfully parsed valid JSON: "+str(data), 3)
            for sensor in data:
                __arduinoData__[sensor["name"]] = sensor["state"]
            break
        else:
            debug("Non-list data from arduino!", 0)

#--ACCESSORY CLASSES--#

#pass
#Handles GPIO-EnvVar relations, as well as delays, read functionality, etc.
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

#pass
#Handles environment variable adjustments in both the up (current < max) and down (current > max) directions, as well as when in range (usually turn things off)
class Actuator:
    def __init__(self, name, funcUp, funcDefault, funcDown, args0 = [], args1 = [], args2 = []):
        self.name = name
        if funcDefault is None:
            debug("No default action for actuator '{}' is defined!".format(name), 0)
            raise Exception
        if(funcUp == None):            #Default all outside-range operations to default (provides redundancy)
            debug("No 'up' function defined for actuator '{}', defaulting to default".format(name), 3)
            funcUp = funcDefault
        if(funcDown == None):
            debug("No 'down' function defined for actuator '{}', defaulting to default".format(name), 3)
            funcDown = funcDefault
        self.func = (funcUp, funcDefault, funcDown)
        #Arg settings
        self.args = (args0, args1, args2)
        #Do default state
        self.actuate(1)
        #Will always be false unless set elsewhere
        self.busy = False
       #handle function rerouting based on envvar state 
       
    @classmethod
    def scheduled(cls, name, funcUp, funcDefault, funcDown, schedule, args0=[], args1=[], args2=[]):
        me = cls(name, funcUp, funcDefault, funcDown, schedule, args0, args1, args2)
        me.schedule = schedule
        me.runningSchedule = False
        return me
    def actuate(self, index):
        if(self.busy is True):
            debug("Actuator {} is busy!".format(self.name), 3)
        elif(index == self.trajectory):
            debug("Actuator {} already has trajectory {}.".format(self.name, self.trajectory), 3)
        else:
            #ALWAYS default to 1
            if index not in (0,1,2): 
                debug("Invalid actuation index of {} detected! Defaulting.".format(index), 0)
                index = 1
            debug("Actuating {} {}, passing {} arguments.".format(self.name, indexToMsg(index), len(args)), 1)
            func[index](*self.args[index])
    def indexToMsg(self, index):
        if index is 0: return 'up'
        elif index is 1: return 'to default'
        elif index is 2: return 'down'
    #Pass
    def autoSchedule(self):
        if(type(self.schedule) is list):
            for item in self.schedule:
                if type(item) is not dict: 
                    debug("Schedule for actuator {} subitem {} is not a list!".format(self.name, self.schedule.index(item)), 0)
                    raise
                    break
                elif "index" not in item.keys():
                    debug("Schedule for actuator {} subitem {} does not contain an actuation index!".format(self.name, self.schedule.index(item)), 0)
                    raise
                    break
                elif "timestamp" not in item.keys():
                    debug("Schedule for actuator {} subitem {} does not contain a timestamp!".format(self.name, self.schedule.index(item)), 0)
                    raise
                    break
        else:
            debug("Schedule for actuator {} is not a list!".format(self.name), 0)
            raise
        self.runningSchedule = True
        thread.start_new_thread(_autoSchedule, ())
    def _autoSchedule(self):
        i = 0
        debug("Running autoscheduler for {}...".format(self.name), 1)
        while self.runningSchedule:
            if(datetime.now().time() > schedule[i]["timestamp"]):
                actuator.actuate(schedule[i]["index"])
                debug("Autoscheduler: Setting actuator {} to index {} at time {}.".format(self.name, schedule[i]["index"], schedule[i]["timestamp"]), 1)
                #increment and bound
                i = (i+1)%len(schedule)
    def haltSchedule(self):
        debug("Halting autoscheduler for {}...".format(self.name), 1)
        self.runningSchedule = False
    def hold(self, time):
        debug("Holding actuator {} at state {} for {}s.".format(self.name, self.trajectory, time), 3)
        thread.start_new_thread(self._hold, (time,))
    def _hold(self, time):
        self.busy = True
        sleep(time)
        self.busy = False

#pass
#Manages the state of environment variables as reported by the sensors relative to their minimum and maximum homeostatic optima
class EnvironmentVariable:
    def __init__(self, name, min, max, optimal, sensor, actuator):
        self.name = name
        self.min = min
        self.sensor = sensor
        if(actuator is None):
            debug("Attached actuator should not be none. Please use EnvironmentVariable.noActuator() classmethod.")
            raise
        self.actuator = actuator
        self.current = optimal
        self.max = max
        self.optimal = optimal
        self.current = sensor.read()
        
    @classmethod
    def noActuator(cls, name, min, max, optimal, sensor, tolerance):
        me = cls(name, min, max, optimal, sensor, None)
        me.tolerance = tolerance
        return me
    #Enacts all steps of the Sense,Plan,Act model
    def update(self):
        if(__setup__):
            
            #Sense
            temp = self.sensor.read()
            if(temp != None):
                self.current = temp
            else:
                debug("'"+self.sensor.name+"' read as None, is this supposed to happen?", 0)
            
            #Plan
            if(self.current >= self.max):
                debug("'"+envvar.name+"' is too high! "+str(self.current)+" >= "+str(self.max), 2)
                index = 2
            elif(self.current <= self.min):
                debug("'"+self.name+"' is too low! "+str(self.current)+" <= "+str(self.min), 2)
                index = 0
            if self.actuator is None: #then must be a 
                if(abs(self.current-self.optimal) < self.tolerance):
                    print("'"+self.name+"' has reached optimal. "+str(self.current)+" is ±"+str(self.tolerance)+" of "+str(self.optimal)+".")
            else:
                if((self.actuator.trajectory == 2 and self.current <= self.optimal) or (self.actuator.trajectory == 0 and self.current >= self.optimal)):
                    print("'"+self.name+"' has reached optimal. "+str(self.current)+" ~ "+str(self.optimal)+". T:"+str(self.trajectory))
                    index = 1
            #Act
            self.actuator.actuate(index)

#pass
#Manages database interactions, and collects and packages all sensor data into a single SQL row-insertion command
class DBManager:
    def __init__(self, settings):
        self.settings = settings
        self.delta = settings['delta']
        try:
            debug("Creating database manager...", 3)
            self.database = mariadb.connect(host = settings["host"], user=settings["user"], password=settings["password"], database=settings["name"])
        except mariadb.Error as error:
            debug("Error connecting to database: '{}'".format(error), 0)
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
        try:
            self.execute(command)
        except mariadb.Error as error:
            debug("Error setting up/creating data table: '{}'".format(error), 0)
        else:
            debug("DB tables set up successfully.", 2)
    def sendSensorData(self, evs):
        if(time() - self.lastUpdate > self.delta)
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
            
            try:
                self.execute(command)
            except mariadb.Error as error:
                debug("Error sending data to data table: {}".format(error))
            else:
                debug("Current sensor data successfully sent to database!", 1)
                
            self.lastUpdate = time()
    def execute(self, command):
        debug("Executing MySQL commmand: "+command, 3)
        self.cursor.execute(command)

#pass
#Manages camera interactions (taking photos and the like)
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
        self.lastCapture = 0
    def capture(self):
        if(time() - self.lastCapture > self.delta):
            if(self.light != None):
                self.light.actuate(0)
                self._capture()
                self.light.actuate(1)
            else:
                self._capture()
            self.lastCapture = time()
    def _capture(self):
        debug("Capturing an image!", 1)
        self.camera.start_preview()
        sleep(3)
        try:
            self.camera.capture(self.formatPath())
        except Error as e:
            debug("Error capturing photo: {}".format(e), 0)
        finally:
            self.camera.stop_preview()
    def formatPath(self):
        return '{0}dave_{1}.jpg'.format(self.path, str(datetime.datetime.now()).split(".")[0].replace(' ','_'))

  
#--MAIN CLASS--#

#pass
class DAVE:
    __init__(self, evs, actuators, debug, delay, ard, db, cam):
        self.evs = evs
        self.scheduledActuators = actuators
        self.debugLevel = debug
        self.delay = delay
        
        debug("Performing setup...", 1)
        if ard is not None:
            self.arduino = ArduinoManager(ard)
        else:
            debug("No arduino settings given! No arduino activity will occur.", 0)
            
        if db is not None: 
            self.database = DatabaseManager(db)
        else:
            debug("No database settings given! No database activity will occur.", 0)
            
        if cam is not None:
            self.camera = CameraManager(cam)
        else:
            debug("No camera settings given! No camera activity will occur.", 0)
            
    def run(self):
        print("Welcome to the DAVE Runtime Environment! Optimal homeostasis will now be generated.") 
        for actuator in self.scheduledActuators:
            actuator.autoSchedule()
        while True:
            for ev in self.evs:
                ev.update()    #Sense
                if(ev.sensor != None):
                    print(ev.name+": "+formatState(ev.current))
                sleep(self.delay)
            self.database.sendSensorData(self.evs)
            self.camera.capture()
    def interface():
        if(__setup__):
            print("Welcome to the DAVE Manual Control Interface!\n")
            while True:
                x=-1
                while x < 0 or x > 6:
                    print("\nWhat would you like do?\n1: Read variable\n2: Actuate\n3: Read latest from MySQL database\n4: Write current to MySQL database\n5: Take a photo\n6: Quit")
                    x = int(input())
                
                if(x == 1):
                    print("Choose an environment variable:")
                    i=-1
                    while i < 0 or i > len(self.evs):
                        i = 1
                        for sensor in self.evs:
                            print(str(i)+": "+sensor.name)
                            i+=1
                        i = int(input())
                    self.evs[i-1].update()
                    print("Attached sensor: "+self.evs[i-1].sensor.name)
                    print("State: "+str(self.evs[i-1].current))
                        
                elif(x == 2):
                    print("Choose an actuator:")
                    #Create compound list of EVs with actuators as well as standalone actuators
                    newList = self.scheduledActuators[:]
                    for ev in self.evs:
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
                        actuator.actuate(c-1)
                elif(x == 6):
                    break
                elif(x == 5):
                    self.camera.capture()
                    print("Captured!")
                elif(x==4):
                    self.database.sendSensorData(self.evs)
                elif(x == 3):
                    try:
                        self.database.cursor.execute("SELECT * FROM sensordata")
                        result = self.database.cursor.fetchall()[-1]
                        print(result)
                    except mariadb.Error as error:
                        debug("MySQL error: {}".format(error), 0)
                    except IndexError as error:
                        debug("Table has no rows!", 0)
            print("Goodbye!")
            sleep(1)
        else:
            print("[ERR]: Setup has not yet been performed!")