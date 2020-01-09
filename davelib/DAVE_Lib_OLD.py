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
                    debug("Missing data in JSON from arduino!", 0)
                    sleep(1)
                    continue
            debug("Sucessfully parsed valid JSON: "+str(data), 3)
            for sensor in data:
                __arduinoData__[sensor["name"]] = sensor["state"]
            break
        else:
            debug("Non-list data from arduino!", 0)

#MAJOR CLASSES - Env Var holds 1 sensor and 1 actuator.

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
            

        
