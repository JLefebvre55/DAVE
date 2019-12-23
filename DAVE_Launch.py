from davelib import DAVE_Lib as dave, DAVE_mk2 as mk2

#EVs = [], debug = False, delay = 0.1
dave.setup(evs = mk2.__EVs__, actuators = mk2.__Actuators__, debug = 1, delay = mk2.__delay__, arduino = mk2.__arduinoInfo__, db = mk2.__dbInfo__)
dave.run()