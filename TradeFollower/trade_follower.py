from account import AccountManager
import pandas as pd
import numpy as np
from datetime import datetime
import time
import MetaTrader5 as mt5
import pyautogui
from multiprocessing import Process, Pipe
from collections import deque
from enum import Enum
from virtual_stop import manage_virtual, update_virtual, VirtualManager
# from . import virtual_stop
# always returns "OK"
# pyautogui.confirm('Asks OK or Cancel')  # returns "OK" or "Cancel"

# pyautogui.password('Enter password')  # returns string or None

"""
TO DO:
Make sure new stop is not updated unless stop is atleast +std in profit
Add automatic position closing at 21:00 utc, and lock out new entries until 22

"""

# =============
# STATIC & GLOBAL VARIABLES
# ================

VERSION = """
          V 0.02
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

# Account Manager
acc_manager = None

manager = VirtualManager()

class PosType(Enum):
    TREND = 0
    MEAN = 1

# ==================
#  Calculation Data Functions
# ==================

def get_format_ohlc(symbol, timeframe, n, curr_time):
    data_raw = mt5.copy_rates_from(symbol, timeframe, curr_time, n)
    columns = data_raw.dtype.names
    # data = pd.DataFrame(data_raw)
    # data['time'] = pd.to_datetime(data['time'], unit='s')
    return columns, np.flip(data_raw)

def calculate_stdev(data,period):
    """
    Calculate stdev of a given series
    """
    a = np.array(data)
    return np.std(a[:period])

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

def calculate_tr(data_in, reverse=True):
    """
    Calculate the True Range,
    Assumes oldest to newest sort. If reverse is set to true, the data passed is newest to oldest and will be reversed before
    calculations take place
    """
    data = data_in.iloc[::-1] if reverse else data_in
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
        return self.data[0][self.columns.index(val)]
    def get_column(self, val, total=0, as_df=False):
        """
            Returns the whole column in an array for the given value, if 0, else
            gives the total specified
        """
        if as_df:
            return self.get_pd()[val]

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
            [list(x)[1:] for x in self.data], 
            columns=list(self.columns[1:]),
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
        self.ema = None
        self.hma = None
        self.atr = None
        self.std = None
    
    def update(self, curr_time):
        data = get_format_ohlc(self.symbol, self.timeframe, 1, curr_time)[1]
        last_time = self.ohlc.get_last('time')
        # print(f"[DATA] Updating with {data[0]}")
        # print(f"[DATA] Current {self.ohlc.data[0]}")

        if data[0][0] > last_time:
            print(f"[DATA] New candle detected {data[0][0]} last time:{last_time}", end="")
            # If time of new bar is newer than last time, append new
            self.ohlc.add_data(data[0])
            self.isReady = True
        else:
            # print(f"[DATA] No new data to update {self.timeframe}. ", end="")
            self.isReady = False
    
    def set_functions(self, **kwargs):
        for key, val in kwargs.items():
            if key == "ema":
                self.ema = calculate_ema(self.ohlc.get_column('close', val+1), val) \
                if self.ema == None else calculate_ema(
                    [self.ema,  self.ohlc.get_last('close')], val, is_ema_value=True
                    )
            elif key == "hma":
                closes =self.ohlc.get_column('close', val, as_df=True).iloc[::-1]
                # print(f"[DATA] Closes to be built into hma: {HMA(closes,val)}")
                self.hma = HMA(closes, val)[-1]
                print(f"\r\n[DATA] self.hma built {self.hma}\r\n")
            elif key == "atr":
                self.atr = calculate_atr(calculate_tr(self.ohlc.get_pd()),val)[0]
            elif key =="std":
                self.std = calculate_stdev(self.ohlc.get_column('close', val+1), val)
    
    def check_target_hit(self, oType, oTime, oPrice, target_dist):
        df = self.ohlc.get_pd()
        bars_since_open = df.loc[df.index > pd.to_datetime(oTime, unit='s')]
        anchor = bars_since_open['high'].max() if oType == 0 else bars_since_open['low'].min()
        if len(bars_since_open) == 0:
            print("No bars since open.")
            return False
        if (oType == 0 and bars_since_open['close'][0] < oPrice ) or (oType == 1 and bars_since_open['close'][0] > oPrice): return False
        print(f"[MANAGER] Target: {target_dist}")
        print(f"[MANAGER] Checking if max distance achieved {anchor} - {oPrice} / {target_dist} = {abs(anchor - oPrice) / target_dist * 100}%")
        return abs(anchor - oPrice) >= target_dist
    
    def get_stop(self, oType, ask, bid, max_stop_dist, pos_type=PosType.TREND):
        """
        Find the best place for a stop, given the direction:
        Buy > min(1 atr or last low in 8 bars - spread)
        Sell > min(1 atr or last high in 8 bars + spread)
        """
        df = self.ohlc.get_pd()

        if oType == 0:
            price = ask
            spread = ask - bid
            lowest = min(df['low'].min() - spread,self.hma - self.std)
            stop = lowest if price - lowest < max_stop_dist else ask - max_stop_dist
            stop = min(df['low'].iloc[:5].min() - spread, self.hma - self.std, price - .33 * max_stop_dist) if pos_type == PosType.MEAN else stop
            print(f"[STOP CALCULATION] buy stop = {stop}")
        else:
            price = bid
            spread = ask - bid
            highest = max(df['high'].max() + spread,self.hma + self.std)
            stop = highest if highest - price < max_stop_dist else bid + max_stop_dist
            stop = max(df['high'].iloc[:5].max() + spread, self.hma+self.std, price + .33 * max_stop_dist) if pos_type == PosType.MEAN else stop
            print(f"[STOP CALCULATION] sell stop = {stop}")
                
        
        return stop
    
    def get_last_bar(self):
        """
        Return most recent ohlc
        """
        return self.ohlc.get_pd().iloc[0]

    

def data_ready(curr_time, symbols):
    try:
        for key in data_keepers:
            if key not in symbols:
                data_keepers.pop(key)

        for s in symbols:
            if not s in data_keepers:
                data_keepers[s] = [ DataKeep(s, mt5.TIMEFRAME_H1, 21, curr_time), DataKeep(s, mt5.TIMEFRAME_M6, 70, curr_time) ]
            else:
                [x.update(curr_time) for x in data_keepers[s]]
    except:
        print("[WARNING] Error occurred updating data keepers.")
    

# ===============
# Order Entry Methods
# ===============

def get_lots(rate, balance, leverage, risk, stop_pips, isJPY= True, trades =2):
        """
        rate is CounterCurrency / AccountCurrency
        Change mult to 10 if a JPY pair
        """
        max_lev = balance * leverage / 100000 / trades
        mult=1 if not isJPY else 100
        cash_risk = risk if risk >= 1 else balance * risk
        cash_risk /= trades
        per_pip = cash_risk / stop_pips
        size = per_pip * rate * mult
        size = 0.01 if size < 0.01 else size
        size = max_lev - 0.01 if size >= max_lev else size
        print(f"[ORDER] max_lev calculated: {max_lev} of {balance} {leverage}")
        print(f"[ORDER] size calculated: {size}")
        return round(size,2)

def confirm_result(result):
    try:
        if not result:
            raise Exception("[CRITICAL] No result when sending order.")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[CRITICAL] {result}")
            raise Exception(result.retcode)
        all_good = True
    except Exception as e:
        print(f"Error sending order request \n{e}")
        all_good = False

    return all_good

def build_request(vol, symbol, oType, sl, tp, price = 0, comment="", action=mt5.TRADE_ACTION_DEAL, position=0):
    digits = mt5.symbol_info(symbol).digits
    tp = round(tp, digits)
    sl = round(sl, digits)
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
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    } 
    if price != 0:
        request['type_filling'] = mt5.ORDER_FILLING_IOC
        del request['price']
    if position != 0 : request['position'] = position
    if comment != "" : request['comment'] = comment
    print(request)  
    # perform the check and display the result 'as is'
    result = mt5.order_send(request)
    return confirm_result(result)


def enter_new_order(dir, symbol, risk, posType=PosType.TREND):
    print(f"Begin enter new order {dir} on {symbol}")
    # is percentage risk
    # call balance and calculate
    account_info = mt5.account_info()._asdict()
    if account_info == None:
        raise Exception(f"Error getting account info. {mt5.last_error()}")
    else:
        print(account_info)
    # Get rate of exchange for symbol
    if 'USD' in symbol:
        arr = symbol.split("USD")
        if arr[-1] == "":
            rate = 1
        else:
            # 1 / last market price
            rate = 1 / mt5.symbol_info(symbol).ask
            
    else:
        counter = symbol[3:]
        rate = mt5.symbol_info(counter+"USD")
        if rate == None: rate = 1 / mt5.symbol_info("USD"+counter).ask
        else: rate = rate.ask
    # print(f"rate found {rate}")
    # Get lots
    if symbol not in data_keepers:
        curr_time = datetime.utcnow()
        data_keepers[symbol] = [ DataKeep(symbol, mt5.TIMEFRAME_H1, 21, curr_time), DataKeep(symbol, mt5.TIMEFRAME_M6, 56, curr_time) ]
    dk = data_keepers[symbol]
    dk[0].set_functions(atr=20)
    ask = mt5.symbol_info(symbol).ask
    bid = mt5.symbol_info(symbol).bid
    dk[1].set_functions(hma=55, ema=8, std=20)
    stop = dk[1].get_stop(dir,ask,bid, dk[0].atr,posType)
    stop_pips = (ask - stop) / mt5.symbol_info(symbol).point if dir == 0 else (stop - bid) / mt5.symbol_info(symbol).point
    lots = get_lots(rate,account_info['margin_free'] * .8,account_info['leverage'],risk,stop_pips,"JPY" in symbol)
    take = ask + dk[0].atr if dir == 0 else ask - dk[0].atr
    comment = "" if posType == PosType.TREND else "mean"
    if not build_request(lots,symbol,dir,stop,take, comment=comment):
        print("Order # 1 not placed.")
    else:
        time.sleep(2)
        if not build_request(lots,symbol,dir,stop,0.0, comment=comment):
            print("Order # 2 not placed.")

# ==========
# Processor functions
# ===========

def com_function(conn):
    # print("Reading command...")
    com_raw = pyautogui.prompt('Enter Command\n\n[ -b -s :SYMBOL_CHARS ]\n[ -r # ]\n[ -a (str,# ]')  # returns string or None
    conn.send(com_raw)
    time.sleep(1.5)

def handler(conn, acc_manager: AccountManager):
    while True:
        val = conn.recv()
        # print("command read")

        if val == 'q':
            print("Exiting Trade Follower.") 
            quit()
        symbol = SYMBOLS[0]
        risk = 0.02
        # -------
        # Translate command
        # -------
        if 'mean' in val:
                # Position is mean reversion
                posType = PosType.MEAN
        else:
            # Position is trend
            posType = PosType.TREND
        
        if '-b' in val:
            # Enter a new buy order
            oType = 0
        elif '-s' in val:
            # Enter a new sell order
            oType = 1
        else:
            # Not an entry command
            oType = -1
        
        if '-a' in val:
            if not '(' in val:
                # Assume no parameters passed
                acc_manager.switch()
            else:
                arr = val.split('(')[1].split(' ')
                if len(arr) > 1:
                    acc_manager.switch(int(arr[0]), arr[1])
                else:
                    # assumes only description passed
                    acc_manager.switch(descrip=arr[0])


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
            try:
                acc_manager.relog()
                enter_new_order(oType, symbol, risk, posType)
            except Exception as e:
                print(f"Position failed to enter.\r\n{e}")
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
        """
        First argument is the message, second is the symbol, the rest are relevant information
        """
        utc_from = datetime.utcnow()
        s = args[0]
        sym = args[1]
        val = f"{utc_from}: {s} \n{args[2:]}"
        print(val)
        with open(f'/logs/{sym}_log.txt', 'a') as f:
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

def update_mean_position(oType, symbol, tickets, vol, open, hma, std, last_bar):
    """
    Update mean reversion position
    When price hits opposite band, stop is placed at low/high
    When price closes beyond mean, move stop loss to max dist of mean +/- spread or open +/- 2 * spread
    """
    ask = mt5.symbol_info(symbol).ask
    bid = mt5.symbol_info(symbol).bid
    spread = ask - bid
    isUpdate = False
    if oType == 0:
        if last_bar['high'] >= hma + std:
            print("[POSITION] Mean position target hit.")
            Log("[POSITION] Mean position target hit.", symbol, oType, last_bar['low'], f'mean: {hma} upper: {hma+std}')
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,last_bar['low'])
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, last_bar['low'])
            isUpdate = True
        elif last_bar['close'] > hma:
            print("[POSITION] Mean position in profit")
            stop = open + 2 * spread
            if hma - spread > stop : stop = hma - spread
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, stop)
            isUpdate = True
    else:
        if last_bar['low'] <= hma - std:
            print("[POSITION] Mean position target hit.")
            Log("[POSITION] Mean position target hit.", symbol, oType, last_bar['high'], f'mean: {hma} lower: {hma-std}')
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,last_bar['high'])
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, last_bar['high'])
            isUpdate = True
        elif last_bar['close'] < hma:
            print("[POSITION] Mean position in profit")
            stop = open - 2 * spread
            if hma + spread < stop : stop = hma + spread
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, stop)
            isUpdate = True
    if isUpdate: print("[POSITION] Mean reversion position updated.")

def update_trend_position(oType, symbol, tickets, stop, open, atr60, hma, std):
    """
    Manage an open trend position,
    Trail price at band when on the positive side of the mean, else at .3 atr60 above/below band
    or price +/- atr15 if price is >= 2*atr15 away from mean
    Move price to break even if price is away from hma by 1 atr60
    """
    ask = mt5.symbol_info(symbol).ask
    bid = mt5.symbol_info(symbol).bid
    spread = ask - bid
    isUpdate = False

    if oType == 0:
        if ask >= hma + atr60 + std:
            # Price is far in profit
            print("[POSITION] Trend Position deep in profit.")
            new_stop = bid - atr60
            if new_stop < open + std or new_stop <= stop:
                print("[POSITION] Trend Buy Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is very far away from mean, updating stop to in profit.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
        elif ask - hma >= atr60:
            print("[POSITION] Trend Position, break even triggered as price is far from mean.")
            Log("[TREND POSITION] Break even triggered.", symbol, open, f"{stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,open + 2 * spread)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, open + 2 * spread)
            isUpdate = True
        elif ask > hma:
            print("[POSITION] Trend Postion, price is on positive side of mean.")
            new_stop = hma - std
            if new_stop < open + std or new_stop <= stop:
                print("[POSITION] Trend Buy Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is on positive side of mean.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
        else:
            print("[POSITION] Trend Position, price is on negative side of mean.")
            new_stop = hma - std - .3 * atr60
            if new_stop <= stop or new_stop <= open:
                print("[POSITION] Trend Buy Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is on negative side of mean.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol, new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
    else:
        if bid <= hma - atr60 -std:
            # Price is far in profit
            print("[POSITION] Trend Position deep in profit.")
            new_stop = ask + std
            if new_stop > open - std or new_stop >= stop:
                print("[POSITION] Trend Sell Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is very far away from mean, updating stop to in profit.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
        elif hma - bid >= atr60:
            print("[POSITION] Trend Position, break even triggered as price is far from mean.")
            Log("[TREND POSITION] Moving stop to break even.", symbol, open, f"{stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,open - 2 * spread)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, open - 2 * spread)
            isUpdate = True
        elif bid < hma:
            print("[POSITION] Trend Postion, price is on positive side of mean.")
            new_stop = hma + std
            if new_stop > open - std or new_stop >= stop:
                print("[POSITION] Trend Sell Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is on positive side of mean.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,hma + std)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, hma + std)
            isUpdate = True
        else:
            print("[POSITION] Trend Position, price is on negative side of mean.")
            new_stop = hma + std + .3 * atr60
            if new_stop >= stop or new_stop >= open:
                print("[POSITION] Trend Sell Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is on negative side of mean.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol, new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True

    if isUpdate: print("[POSITION] Trend position updating successfully.")

    
def update_runner_position(oType, symbol, ticket, vol, open, trail_dist, hma):
    """
        Update runner type of positions,
        Follows hma by .25 atr
        close when price closes over HMA
    """
    print(f"[MANAGER] Runner Position to update:\r\n{ticket}:{mt5.positions_get(ticket=ticket)}")
    isUpdate = True
    if oType == 0:
        price = mt5.symbol_info_tick(symbol).ask
        if price < hma:
            # close_res = build_request(vol,symbol,1,0.0,0.0,price=open,action=mt5.TRADE_ACTION_DEAL,position=ticket)
            close_res = mt5.Close(symbol, ticket=ticket)
            if not close_res:
                Log("[Critical] Error when closing runner", symbol, oType, price, f'mean:{hma}')
                isUpdate = False
                
            else:
                print("[POSITION] Buy runner closed.")
        else:
            new_stop = hma - trail_dist if hma - trail_dist > open + trail_dist else open + trail_dist
            update_res = build_request(vol,symbol,1,new_stop,0.0, action=mt5.TRADE_ACTION_SLTP, position=ticket, comment="runner")
            if not update_res:
                Log("[Critical] Error when updating runner", symbol, oType, new_stop, f'mean:{hma}', f'newstop:{new_stop}')
                isUpdate = False
                # Add Virtual Stop
                manage_virtual(manager,ticket,oType,symbol,new_stop)
            else:
                print("[POSITION] Buy runner updated.")
    else:
        price = mt5.symbol_info_tick(symbol).bid
        if price < hma:
            # close_res = build_request(vol,symbol,0,0.0,0.0,price=open,action=mt5.TRADE_ACTION_DEAL,position=ticket)
            close_res = mt5.Close(symbol, ticket=ticket)
            if not close_res:
                Log("[Critical] Error when closing runner", symbol, oType, price, f'mean:{hma}')
                isUpdate = False
            else:
                print("[POSITION] Sell runner closed.")
        else:
            new_stop = hma -+trail_dist if hma + trail_dist < open - trail_dist else open - trail_dist
            update_res = build_request(vol,symbol,0,new_stop,0.0,action=mt5.TRADE_ACTION_SLTP, position=ticket, comment="runner")
            if not update_res:
                Log("[Critical] Error when updating runner", symbol, oType, price, f'mean:{hma}', f'newstop:{new_stop}')
                isUpdate = False
                # Add Virtual Stop
                manage_virtual(manager,ticket,oType,symbol,new_stop)
            else:
                print("[POSITION] Sell runner updated.")
    
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
    for sym in positions['symbol']:
        if sym not in arr: arr.append(sym)
    return arr

# ================
# Main Loop
# ================

if __name__ == "__main__":
    print(f"Begin Trade Follower \r\n{VERSION}")

    acc_manager = AccountManager()

    com_process = None
    par_con, chi_con = Pipe()
    handler_process = Process(target=handler, args=[par_con, acc_manager])
    handler_process.daemon = True
    handler_process.start()

    virtual_count = 0
    no_pos_count = 0

    while handler_process.is_alive():
        
        if not com_process or not com_process.is_alive():
            com_process = Process(target=com_function, args=[chi_con])
            com_process.daemon = True
            com_process.start()
        
        # Do Management work here
        utc_from = datetime.utcnow()
        positions = mt5.positions_get()
        if positions:
            pos_df = get_positions(positions)
            pos_symbols = extract_symbols(pos_df)
            virtual_count += 1
            time.sleep(1)
            if virtual_count % 30 == 0:
                print(f"open positions: {pos_symbols}")
                update_virtual(manager)
            if virtual_count > 300: virtual_count = 0
        else:
            no_pos_count += 1
            if no_pos_count % 300 == 0:
                print("No positions.")
            if no_pos_count > 600: no_pos_count = 0
            time.sleep(5)
            continue

        # Check for readied data
        data_ready(utc_from, pos_symbols)
        # print("[DATA] Datakeepers ready.")
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
                "mean" use mean reversion rules to handle this position
            """
            # Ready data keepers
            dk = data_keepers[sym]
            if not dk[1].isReady: continue
            dk[0].set_functions(atr=20)
            dk[1].set_functions(hma=55, ema=8, atr=20, std=20)
            # Grab symbol info
            # print(pos_df.head(3))
  
            sym_pos = pos_df.loc[pos_df['symbol'] == sym]
            print(sym_pos)
            tickets = sym_pos['ticket']
            o = sym_pos['price_open']
            oTime = sym_pos['time']
            oType = sym_pos['type'].iloc[0]
            tp = sym_pos['tp']
            sl = sym_pos['sl']
            vol = sym_pos['volume'].iloc[0]
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
                print("[POSITION] updating runnner.")
                update_runner_position(oType, sym, int(tickets.iloc[0]), vol, o.iloc[0],.25* dk[0].atr, dk[1].hma)
            
            if "mean" in comment:
                print("[POSITION] Updating Mean Reversion postion.")
                update_mean_position(oType, sym, tickets, vol, o.iloc[0], dk[1].hma, dk[1].std, dk[1].get_last_bar())
                continue

            # Check if target has been hit, and if there is more than one open position on symbol
            target = tp[tp.gt(0).idxmax()]
            if target == 0: 
                # check comment for target instructions, else return atr
                if "target=1" in comment:
                    target = abs(sl.iloc[0] - o.iloc[0])
                if "target=2" in comment:
                    target = 2 * abs(sl.iloc[0] - o.iloc[0])
                else:
                    target = dk[0].atr
            else:
                target = abs(target - o.iloc[0])
            print("[POSITION] Checking if target reached.")
            if dk[1].check_target_hit(oType, oTime.iloc[0],o.iloc[0], target):
                Log("[INFO] Target hit", sym, oType, oTime.iloc[0])
                if len(sym_pos) > 1:
                    # Close one position, and move other to break even, with a 0 tp
                    print("[POSITION] Updating to Break Even Position")
                    set_profit_position(
                        vol,sym_pos['symbol'].iloc[0],oType,int(tickets.iloc[0]),int(tickets.iloc[1]),.2 * dk[0].atr
                        )
                elif "runner" not in comment:
                    print("[POSITION] Updating position to Runner.")
                    Log("[INFO] Updated position to runner", sym, oType, oTime.iloc[0])
                    update_runner_position(oType, sym, int(tickets.iloc[0]), vol, o.iloc[0], .25 * dk[0].atr, dk[1].hma)
            else:
                print("[POSITION] Still alive, no target has been hit.")
            
            # Assume trend position, use trend following rules to update if its gotten this far
            
            update_trend_position(oType, sym, tickets, sl.iloc[0], o.iloc[0], dk[0].atr, dk[1].hma, dk[1].std)

                # >>>>>>>>>>>>>>>>>>>>>>>>>>
                # Capture important data here
                # >>>>>>>>>>>>>>>>>>>>>>>>>>>
        
        # print(f"End of main loop. handler? {handler_process.is_alive()} commander? {com_process.is_alive()}")
        time.sleep(1)


    
