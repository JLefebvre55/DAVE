from davelib import DAVE_Lib as dave, DAVE_mk1 as mk1

#EVs = [], debug = False, delay = 0.1
dave.DAVE(mk1.__standardEVs__, True, 1)
dave.run()