from davelib import DAVE_Lib as dave, DAVE_mk3 as settings

#EVs = [], debug = False, delay = 0.1
dave.setup(evs = settings.__EVs__, actuators = settings.__Actuators__, debug = 1, delay = settings.__delay__, arduino = settings.__arduinoInfo__, db = settings.__dbInfo__)
dave.run()