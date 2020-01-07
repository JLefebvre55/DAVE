from davelib import DAVE_Lib as dave, DAVE_mk3 as settings

#evs, debug, delay, arduino, db
dave.setup(evs = settings.__EVs__, actuators = settings.__Actuators__, debug = 3, delay = settings.__delay__, arduino = settings.__arduinoInfo__, db = settings.__dbInfo__)
dave.interface()