import pandas as pd
import MetaTrader5 as mt5
from multiprocessing import Process
from PositionManager.position import get_positions
from PositionManager.command import *

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
def init_settings():
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
    return {
        'timeframe':TimeFrame,
        'meanPeriod':MeanPeriod,
        'trailDist':TrailDist,
        'stopDist':StopDist,
        'takeDist':TakeDist,
        'EarlyBreak':EarlyBreak
    }

# ========================
# Check and manage all open Positions
# ========================

def manage_open_positions():
    positions = mt5.positions_get()
    if positions==None:
        # Give all the formatted positions to the manager
        m = Manager(get_positions)

def main_management():
    print("MT5 Position Manger Booting...")
    while online:
        do_work()
def main_command():
    settings = init_settings()
    while online:
        print("Ready for command | 'help' for list of commands\r\n")
        val = input("==>  ")
        Command(settings, val)

if __name__ == '__main__':
    pM = Process(target=main_management, name='Open Position Management')
    pC = Process(target=main_command, name='Command Listener')

