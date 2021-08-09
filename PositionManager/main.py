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
    
def do_work(manager):
    if manager == None:
        print("No open positions.")
    print(f"Checking open positions: {mt5.positions_total}")
    symbol_data = {}
    for sym in manager.symbols:
        sym
    # copy_rates_from(
    #     symbol,       // symbol name
    #     timeframe,    // timeframe
    #     date_from,    // initial bar open date
    #     count         // number of bars
    # )

# ====================
# Init settings
# ===================

print("--INIT SETTINGS--")
print("Press enter to pass init.")
TimeFrame = 60
MeanPeriod = 55
TrailDist = 1.5 # ATR
StopDist = 1.5
TakeDist = 1
EarlyBreak = True
# display init settings
print(
    f"""
    Time Frame : {TimeFrame}
    Mean (EMA) Period : {MeanPeriod}
    ....Exits are in mults of ATR....
    Trail Distance: {TrailDist}
    Stop Distance: {StopDist}
    Take Distance: {TakeDist}
    Move Position to break even if in profit and early exit detected? {EarlyBreak}
    """
)
if input("[setting name] (new val)").strip != "":
    print("Init settings would be updated here.")


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
