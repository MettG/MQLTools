import pandas as pd
import MetaTrader5 as mt5
from PositionManager.position import get_positions

if not mt5.initialize():
    print("init failed.")
    mt5.shutdown()

# request connection status and parameters
print(mt5.terminal_info())
# get data on MetaTrader 5 version
print(mt5.version())
online = True
# ======================
# Start Management Loop
# ======================

def do_work():
    print(f"Checking positions: {mt5.positions_total}")
    pos = gather_positions()

# ========================
# Check and manage all open Positions
# ========================

positions = mt5.positions_get()
if positions==None:
    # Give all the formatted positions to the manager
    m = Manager(get_positions)

while online:
    do_work()
