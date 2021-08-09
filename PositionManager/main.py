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
# Management Loop
# ======================

def do_work():
    print(f"Checking positions: {mt5.positions_total}")
    

# ========================
# Check and manage all open Positions
# ========================

def manage_open_positions():
    positions = mt5.positions_get()
    if positions==None:
        # Give all the formatted positions to the manager
        m = Manager(get_positions)

def main():
    print("MT5 Position Manger Booting...")
    
    while online:
        do_work()

if __name__ == '__main__':
    main()
