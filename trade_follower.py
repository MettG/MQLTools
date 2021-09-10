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
          Places stop min of (highest/lowest +/- spread of last 8 or 1 * atr)
          Places take max of (highest/lowest of last 8 or 1 * atr) as default, further options soon to come
          Trails open orders by .25 * atr (1hr) above/below HMA 55
          close orders when ema over/under hma and close over/under hma (after profit has been hit previously in the last 8 bars)
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
#  Calculation Data Functions
# ==================

def get_format_ohlc(symbol, timeframe, n, curr_time):
    data_raw = mt5.copy_rates_from(symbol, timeframe, curr_time, n)
    columns = data_raw.dtype.names
    # data = pd.DataFrame(data_raw)
    # data['time'] = pd.to_datetime(data['time'], unit='s')
    return columns, np.flip(data_raw)

def calculate_ema(data, period, smoothing=2, is_ema_value=False):
    """
    Calculate EMA of a given series, if is_ema_value = true, 
    data is [prev_ema, new_data_value]
    Wants data of 0 - most recent to x - most past
    """
    ema = [sum(data[:period])/period] if not is_ema_value else [data[0]]

    if not is_ema_value:
        for d in data[period:]:
            ema.append((d * (smoothing / (1 + period))) + ema[-1] * (1 - (smoothing / (1 + period))))
    else:
        ema.append((data[1] * (smoothing / (1 + period))) + ema[-1] * (1 - (smoothing / (1 + period))))
    return ema[-1]

def WMA(data, period):
       return data.rolling(period).apply(lambda x: ((np.arange(period)+1)*x).sum()/(np.arange(period)+1).sum(), raw=True)

def HMA(data, period):
       return WMA(WMA(data, period//2).multiply(2).sub(WMA(data, period)), int(np.sqrt(period)))

def calculate_tr(data):
    """
    Calculate the True Range
    """
    high_low = data['high'] - data['low']
    high_close = (data['high'] - data['close'].shift()).abs()
    low_close = (data['low'] - data['close'].shift()).abs()
    ranges = pd.concat([high_close,high_low,low_close], axis=1)
    true_range = ranges.max(axis=1)
    # Swap data around so that it is from to most recent to oldest
    return true_range.iloc[::-1]

def calculate_atr(true_range,period):
    """
    Calculate the ATR given true_range data
    """
    atr = true_range.rolling(period).sum()/period
    # Swap data around so that it is from to most recent to oldest
    return atr.iloc[::-1]

# ==================
#  Data Keeping Functions
# ==================

# Holds all the data necessary for open positions
data_keepers = {}

class ColumnQueue:
    """
        Holds all keys as column names
        and then an array of tuples whose values match the columns
    """
    def __init__(self, columns, data, max):
        self.columns = columns
        self.data = deque(data, maxlen=max)
    def add_data(self, data):
        self.data.appendleft(data)
    def get_last(self, val):
        """
            Returns last value of data array for the given value name
            ie. "close", "low"
        """
        return self.data[-1][self.columns.index(val)]
    def get_column(self, val, total=0):
        """
            Returns the whole column in an array for the given value, if 0, else
            gives the total specified
        """
        arr = []
        for x in self.data:
            if total != 0 and len(arr) > total:
                break
            arr.append(x[self.columns.index(val)])
        return arr
    def get_pd(self):
        """
            Get a pandas data frame, where time is index (first item in tuple)
        """
        return pd.DataFrame(
            [x[1:] for x in self.data], 
            columns=list(self.columns),
            index=[pd.to_datetime(x[0], unit='s') for x in self.data]
            )


class DataKeep:
    """
        Hold a deque of bars, update as necessary
        Calculate the indicators as required
    """
    def __init__(self, symbol, timeframe, number, curr_time):
        self.symbol = symbol
        self.timeframe = timeframe
        columns, data = get_format_ohlc(symbol, timeframe, number, curr_time)
        self.ohlc = ColumnQueue(columns, data, number)
        self.isReady = True
    
    def update(self, curr_time):
        data = get_format_ohlc(self.symbol, self.timeframe, 1, curr_time)[0]
        if data[0] > self.ohlc.get_last('time'):
            # If time of new bar is newer than last time, append new
            self.ohlc.add_data(data)
            self.isReady = True
        else:
            print(f"No new data to update {self.timeframe}. ", end="")
            self.isReady = False
    
    def set_functions(self, *kwargs):
        for key, val in kwargs.items():
            if key == "ema":
                self.ema = calculate_ema(
                    [self.ema,  self.ohlc.get_last('close')], val, is_ema_value=True
                    ) \
                if self.ema else calculate_ema(self.ohlc.get_column('close', val+1), val)
            elif key == "hma":
                self.hma = HMA(self.ohlc.get_column('close', val), val)
            elif key == "atr":
                self.atr = calculate_atr(calculate_tr(self.ohlc.get_pd()),val)
    
    def check_target_hit(self, oType, oTime, oPrice, target_dist):
        df = self.ohlc.get_pd()
        bars_since_open = df.loc[df.index > pd.to_datetime(oTime, unit='s')]
        anchor = bars_since_open['high'].max() if oType == 0 else bars_since_open['low'].min()

        return abs(anchor - oPrice) >= target_dist

    

def data_ready(curr_time, symbols):

    for key in data_keepers:
        if key not in symbols:
            data_keepers.pop(key)

    for s in symbols:
        if not data_keepers.has_key(s):
            data_keepers[s] = [ DataKeep(s, mt5.TIMEFRAME_H1, 21, curr_time), DataKeep(s, mt5.TIMEFRAME_M6, 56, curr_time) ]
        else:
            [x.update(curr_time) for x in data_keepers[s]]
    

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

def confirm_result(result):
    try:
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise Exception(result.retcode)
        all_good = True
    except Exception as e:
        print(f"Error sending order request \n{e}")
        all_good = False

    return all_good

def build_request(vol, symbol, oType, sl, tp, comment="", action=mt5.TRADE_ACTION_DEAL, position=0):
    price = mt5.symbol_info_tick(symbol).ask if oType > 0 else mt5.symbol_info_tick(symbol).bid
    request = {
        "action": action,
        "symbol": symbol,
        "volume": vol,
        "type": oType,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 7,
        "magic": 0,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }   
    if position != 0 : request['position'] = position
    # perform the check and display the result 'as is'
    result = mt5.order_send(request)
    return confirm_result(result)


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
    else:
        counter = symbol[3:]
        try:
            rate = mt5.symbol_info(counter+"USD").last
        except:
            rate = 1 / mt5.symbol_info("USD"+counter).last
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
# Log Functions
# ================

class Log:
    """
        Takes care of all logging, takes a list of args, to be displayed in order
    """
    def __init__(self, *args):
        utc_from = datetime.utcnow()
        s = args[0]
        sym = args[1]
        val = f"{utc_from}: {s} \n{args[2:]}"
        print(val)
        with open(f'{sym}_log.txt', 'a') as f:
            f.write("\r\n")
            f.write(val)
            f.write("\r\n")
        

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

def update_runner_position(oType, symbol, ticket, vol, open, trail_dist, hma):
    """
        Update runner type of positions,
        Follows hma by .25 atr
        close when price closes over HMA
    """
    isUpdate = True
    if oType == 0:
        price = mt5.symbol_info_tick(symbol).ask
        if price < hma:
            close_res = build_request(vol,symbol,1,0,0,action=mt5.TRADE_ACTION_DEAL,position=ticket)
            if not close_res:
                Log("[Critical] Error when closing runner", symbol, oType, price, f'mean:{hma}')
                isUpdate = True
        else:
            new_stop = hma - trail_dist if hma - trail_dist > open + trail_dist else open + trail_dist
            update_res = build_request(vol,symbol,oType,new_stop,0,action=mt5.TRADE_ACTION_SLTP, position=ticket, comment="runner")
            if not update_res:
                Log("[Critical] Error when updating runner", symbol, oType, price, f'mean:{hma}', f'newstop:{new_stop}')
                isUpdate = True
    else:
        price = mt5.symbol_info_tick(symbol).bid
        if price < hma:
            close_res = build_request(vol,symbol,0,0,0,action=mt5.TRADE_ACTION_DEAL,position=ticket)
            if not close_res:
                Log("[Critical] Error when closing runner", symbol, oType, price, f'mean:{hma}')
                isUpdate = True
        else:
            new_stop = hma -+trail_dist if hma + trail_dist < open - trail_dist else open - trail_dist
            update_res = build_request(vol,symbol,oType,new_stop,0,action=mt5.TRADE_ACTION_SLTP, position=ticket, comment="runner")
            if not update_res:
                Log("[Critical] Error when updating runner", symbol, oType, price, f'mean:{hma}', f'newstop:{new_stop}')
                isUpdate = True
    
    if isUpdate: print("[POSITION] Runner updated or closed successfully.")


def set_profit_position(vol, symbol, oType, ticket_to_close, ticket_to_even, break_dist):
    price = mt5.symbol_info_tick(symbol).ask if oType > 0 else mt5.symbol_info_tick(symbol).bid
    sl = price + break_dist if oType > 0 else price - break_dist
    closeType = 0 if oType > 0 else 1
    close_res = build_request(vol,symbol,closeType,0,0,action=mt5.TRADE_ACTION_DEAL,position=ticket_to_close)
    even_res = build_request(vol,symbol,oType,sl,0,action=mt5.TRADE_ACTION_SLTP, position=ticket_to_even, comment="runner")
    isError = False
    if not close_res:
        Log("[CRITICAL] Error when closing for 1st profit", symbol, oType, price)
        isError = True
    if not even_res:
        Log("[CRITICAL] Error when updating break even", symbol, oType, price)
        isError = True
    if not isError: print("[POSITION] Position successfull set to profit type.")
 

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

        # Check for readied data
        data_ready(utc_from)

        for sym in data_keepers:
            """
                For each symbol, check if data ready, then perform management on position
                datakeeprs are sym:[1hr dk with atr, 6min dk with ema 8 and hma 55]
                Positon:
                (
                    ticket  time  type  magic  identifier  reason  volume  price_open
                    sl  tp  price_current  swap  profit  symbol comment
                )
                comments will hold special information for management:
                "target=2" means target is two times the distance of the stop
                "target=1" means target is one times the distance of the stop
                "counter" means the position is a counter trend move and should be closed after a price action rejection
            """
            # Readt data keepers
            dk = data_keepers[sym]
            if not dk[1].isReady: continue
            dk[0].set_functions(atr=20)
            dk[1].set_functions(hma=55, ema=8)
            # Grab symbol info
            sym_pos = positions.loc[positions['symbol'] == sym]
            tickets = sym_pos['ticket']
            o = sym_pos['price_open']
            oTime = sym_pos['time']
            oType = sym_pos['type'][0]
            tp = sym_pos['tp']
            sl = sym_pos['sl']
            vol = sym_pos['volume'][0]
            comment = sym_pos['comment'].values
            # >>>>>>>
            # >>>>>>>
            # >>>>>>>
                # # check for no stop, determine best type of manager given market conditions
                # Others to include: Counter 
            # >>>>>>>
            # >>>>>>>
            # >>>>>>>
            # check for runner
            if "runner" in comment:
                # should be only one position in sym_pos
                update_runner_position(oType, vol, o[0], sl[0], dk[0].atr)

            # Check if target has been hit, and if there is more than one open position on symbol
            target = tp[tp.gt(0).idxmax()]
            if target == 0: 
                # check comment for target instructions, else return atr
                if "target=1" in comment:
                    target = abs(sl[0] - o[0])
                if "target=2" in comment:
                    target = 2 * abs(sl[0] - o[0])
                else:
                    target = dk[0].atr
            if dk[1].check_target_hit(oType, oTime[0],o[0], target) and len(sym_pos) > 1:
                # Close one position, and move other to break even, with a 0 tp
                set_profit_position(
                    vol,sym_pos['symbol'][0],oType,tickets[0],tickets[1],.2 * dk[0].atr
                    )
            
            

            
        # print(f"End of main loop. handler? {handler_process.is_alive()} commander? {com_process.is_alive()}")
        time.sleep(1)


    
