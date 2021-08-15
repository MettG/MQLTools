"""
Handle and hold all data for the manager
"""
import MetaTrader5 as mt5
from collections import deque
from datetime import datetime
import pandas as pd
from PositionManager.utils import *

class DataPiece:
    def __init__(self, timeOf, val):
        self.time = timeOf
        self.value = timeOf

class DataHandler:
    def __init__(self, symbol, curr_time, hma_period=55, ema_period=9, atr_period=20):
        # Used for stops
        self.ohlc_60 = deque([],maxlen=atr_period)
        self.atr = 0
        self.symbol = symbol

        # Used for exit strategy
        self.ohlc_6 = deque([], maxlen=hma_period)
        self.ema = deque([], maxlen=ema_period+1)
        self.hma = deque([], maxlen=2)

        # Load data
        self.load_60(curr_time, atr_period)
        self.load_6(curr_time, hma_period)
    
    def load_60(self, curr_time, n):
        """
        Load all 1hr ohlc data
        Calculate atr
        Data is 0 -> len as latest -> most recent
        """
        # Make sure only the necessary number of bars is being grabbed
        n = self.ohlc_60.maxlen - len(self.ohlc_60) + 1
        data_raw = mt5.copy_rates_from(self.symbol, mt5.TIMEFRAME_H1, curr_time, n)
        data = pd.DataFrame(data_raw)
        data['time'] = pd.to_datetime(data['time'], unit='s')
        if len(self.ohlc_60) < self.ohlc_60.maxlen:
            # is preload
            for d in data.iloc[::-1]:
                # Fill up the deque
                if len(self.ohlc_60) >= self.ohlc_60.maxlen:
                    # deeue is full
                    break
                self.ohlc_60.append(d)
        else:
            # is update
            self.ohlc_60.appendleft(data.iloc[[-1]])
        # print(data.head(5))

    def load_6(self, curr_time, n):
        """
        Load all 6 ohlc data
        Calculate hma and ema
        Data is 0 -> len as latest -> most recent
        """
        # Make sure only the necessary number of bars is being grabbed
        n = self.ohlc_6.maxlen - len(self.ohlc_6) + 1
        data_raw = mt5.copy_rates_from(self.symbol, mt5.TIMEFRAME_M6, curr_time, n)
        data = pd.DataFrame(data_raw)
        data['time'] = pd.to_datetime(data['time'], unit='s')
        # print(data.head(5))
        if len(self.ohlc_6) < self.ohlc_6.maxlen:
            # check if update or preload
            for d in data.iloc[::-1]:
                # Fill up the deque
                if len(self.ohlc_6) >= self.ohlc_6.maxlen:
                    break
                self.ohlc_6.append(d)
        else:
            # is update
            self.ohlc_6.appendleft(data.iloc[[-1]])

if __name__ == "__main__":
    # If not an import, assume testing
    if not mt5.initialize():
        print("mt5 failed to init")
        quit()
    
    # Create a data handler
    d = DataHandler("EURUSD", datetime.utcnow())



    
