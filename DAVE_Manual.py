from davelib import DAVE_Lib as dave, DAVE_mk1 as mk1

#EVs = [], debug = False, delay = 0.1
dave.setup(mk1.__standardEVs__, 1, 1)
dave.interface()