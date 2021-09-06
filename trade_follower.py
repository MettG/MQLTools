import pandas as pd
import numpy as np
from datetime import datetime
import time
import MetaTrader5 as mt5
import pyautogui
from multiprocessing import Process, Pipe
from collections import deque

 # always returns "OK"
# pyautogui.confirm('Asks OK or Cancel')  # returns "OK" or "Cancel"

# pyautogui.password('Enter password')  # returns string or None

# =============
# STATIC VARIABLES
# ================

VERSION = """
          V 0.01
          Places stops
          Trails open orders by .25 * atr (1hr) above/below HMA 55
          """

# Array of all symbols
SYMBOLS = [
    "USDJPY","GBPJPY", "EURJPY",
    "GBPUSD", "EURUSD", "AUDUSD",
    "USDCAD", "XAUUSD"
]

ACCOUNT = 1088545
PASSWORD = "pork5659"

# ==================
#  Data Keeping Functions
# ==================

def get_format_ohlc(symbol, timeframe, n, curr_time):
    data_raw = mt5.copy_rates_from(symbol, timeframe, curr_time, n)
    columns = data_raw.dtype.names
    # data = pd.DataFrame(data_raw)
    # data['time'] = pd.to_datetime(data['time'], unit='s')
    return columns, np.flip(data_raw)

# Holds all the data necessary for open positions
data_keepers = {}

class DataKeep:
    """
        Hold a deque of bars, update as necessary
        Calculate the indicators as required
    """
    def __init__(self, symbol, timeframe, number, curr_time):
        self.symbol = symbol
        self.timeframe = timeframe
        columns, data = get_format_ohlc(symbol, timeframe, number, curr_time)
        self.ohlc = (columns, deque(data, maxlen=number)) # Columns, raw data
    
    def update(self, curr_time):
        data = get_format_ohlc(self.symbol, self.timeframe, 1, curr_time)[0]
        if data[0] > self.ohlc[1][0][0]:
            # If time of new bar is newer than time append
            self.ohlc[1].appendleft(data)
        else:
            print(f"No new data to update {self.timeframe}. ", end="")

def data_ready(curr_time, symbols):

    for key in data_keepers:
        if key not in symbols:
            data_keepers.pop(key)


    for s in symbols:
        if not data_keepers.has_key(s):
            data_keepers[s] = [ DataKeep(s, mt5.TIMEFRAME_H1, 21, curr_time), DataKeep(s, mt5.TIMEFRAME_M6, 56, curr_time) ]
        else:
            [x.update(curr_time) for x in data_keepers[s]]


    # Given the current time, determine if there is a new bar yet
    hr_rate = mt5.copy_rates_from_pos("GBPUSD", mt5.TIMEFRAME_H1, 0, 1)
    m6_rate = mt5.copy_rates_from_pos("GBPUSD", mt5.TIMEFRAME_M6, 0, 1)
    # print(hr_rate, m6_rate, mt5.last_error())
    print(DataKeep("GBPUSD", mt5.TIMEFRAME_H1, 21, curr_time).ohlc)


# ===============
# Order Entry Methods
# ===============

def get_lots(rate, balance, risk, stop_pips, isJPY= True, trades =2):
        """
        rate is CounterCurrency / AccountCurrency
        Change mult to 10 if a JPY pair
        """
        mult=.1 if not isJPY else 10
        cash_risk = risk if risk >= 1 else balance * risk
        cash_risk /= trades
        per_pip = cash_risk / stop_pips
        size = per_pip * rate * mult
        size = 0.01 if size < 0.01 else size
        return size

def enter_new_order(dir, symbol, posType, risk):
    if risk < 1:
        # is percentage risk
        # call balance and calculate
        account_info = mt5.account_info()._asdict()
        if account_info == None:
            raise Exception(f"Error getting account info. {mt5.last_error()}")
        else:
            print(account_info['margin_free'])
    # Get rate of exchange for symbol
    if 'USD' in symbol:
        arr = symbol.split("USD")
        if arr[-1] == "":
            rate = 1
        else:
            # 1 / last market price
            rate = 1 / mt5.symbol_info(symbol).last
    print(f"rate found {rate}")

    # Get lots
    # lots = get_lots(rate,)

# ==========
# Processor functions
# ===========

def mt5_login_init():
    # establish connection to the MetaTrader 5 terminal
    if not mt5.initialize():
        print("initialize() failed, error code =",mt5.last_error())
        quit()
    authorized = mt5.login(ACCOUNT, password=PASSWORD)
    if not authorized:
        raise Exception(f"login failed {mt5.last_error()}")
    print(f"Login={authorized}")

def com_function(conn):
    # print("Reading command...")
    com_raw = pyautogui.prompt('Enter Command\n\n[ -b -s -r :SYMBOL_CHARS ]')  # returns string or None
    conn.send(com_raw)
    time.sleep(1.5)

def handler(conn):
    while True:
        val = conn.recv()
        # print("command read")

        mt5_login_init()

        if val == 'q':
            print("Exiting Trade Follower.") 
            quit()
        symbol = SYMBOLS[0]
        risk = 0.02
        # -------
        # Translate command
        # -------
        if 'wide' in val:
                # Position is wide type, with a long stop and less strict exit rules
                posType = 0
        elif 'tight' in val:
            # Position is tight type, with a short stop and strict exit rules (for counter trend and mean reversion trades)
            posType = 1
        else:
            # Position is standard, move to break even after .5 * atr
            posType = 2
        
        if '-b' in val:
            # Enter a new buy order
            oType = 0
        elif '-s' in val:
            # Enter a new sell order
            oType = 1
        else:
            # Not an entry command
            oType = -1

        if '-r' in val:
            # Adjust risk value by the superceding value
            arr = val.split("-r")[-1].split(" ")
            risk = float(arr[1])
        if ':' in val:
            # Parse command for the symbol
            arr = val.split(":")[-1].split(" ")
            sym_chars = arr[0]
            sym_choices = []
 
            for sym in SYMBOLS:
                if sym_chars.upper() in sym:
                    sym_choices.append(sym)
            
            if len(sym_choices) > 1:
                print(f"Multiple symbols detected. Please use more precision ':symbol' \n{sym_choices}")
                continue
            else:
                symbol = sym_choices[0]

        if oType != -1:
            print(f"New Order detected on {symbol}")
            enter_new_order(oType, symbol, posType, risk)
        else:
            print("No order command detected.")

# =================
# Position Functions
# ================

def get_positions(positions):
    """
    Convert tuple of postions to panda dataframe
    """
    # display these positions as a table using pandas.DataFrame
    df=pd.DataFrame(list(positions),columns=positions[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
    return df

def extract_symbols(positions):
    arr = []
    for pos in positions:
        if pos.symbol not in arr: arr.append(pos.symbol)
    return arr

# ================
# Main Loop
# ================

if __name__ == "__main__":
    print(f"Begin Trade Follower \r\n{VERSION}")

    mt5_login_init()

    com_process = None
    par_con, chi_con = Pipe()
    handler_process = Process(target=handler, args=[par_con])
    handler_process.daemon = True
    handler_process.start()
    while handler_process.is_alive():
        
        if not com_process or not com_process.is_alive():
            com_process = Process(target=com_function, args=[chi_con])
            com_process.daemon = True
            com_process.start()
        
        # Do Management work here
        utc_from = datetime.utcnow()
        positions = mt5.positions_get()
        if positions:
            print(positions)
            pos_df = get_positions(positions)
            pos_symbols = extract_symbols(pos_df)

        data_ready(utc_from)


        # print(f"End of main loop. handler? {handler_process.is_alive()} commander? {com_process.is_alive()}")
        time.sleep(1)


    
