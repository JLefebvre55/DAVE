from davelib import DAVE_Lib as dave, DAVE_mk2 as s

#evs, debug, delay, arduino, db
me = dave.DAVE(s.evs, s.acts, 1, 0.1, s.ard, s.db, s.cam)
me.run()
