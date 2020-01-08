from davelib import DAVE_Lib as dave, DAVE_mk3 as settings

#EVs = [], debug = False, delay = 0.1
dave.setup(evs = settings.EVs, actuators = settings.Actuators, debug = 3, delay = settings.delay, arduino = settings.arduinoInfo, db = settings.dbInfo, cam = settings.cameraInfo)
dave.run()