from davelib import DAVE_Lib as dave, DAVE_mk1 as mk1

#evs, debug, delay, arduino, db
dave.setup(evs = mk2.__EVs__, debug = 1, delay = mk2.__delay__, arduino = mk2.__arduinoInfo__, db = mk2.__dbInfo__)
dave.interface()