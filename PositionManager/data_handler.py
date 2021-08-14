"""
Handle and hold all data for the manager
"""
import MetaTrader5 as mt5
from collections import deque

class DataPiece:
    def __init__(self, timeOf, val):
        self.time = timeOf
        self.value = timeOf


class DataHandler:
    def __init__(self, symbol, curr_time, hma_period=55, ema_period=9, atr_period=20):
        # Used for stops
        self.ohlc_60 = deque([])
        self.ohlc_60.maxlen = atr_period
        self.atr = 0

        self.symbol = symbol

        # Used for exit strategy
        self.ohlc_6 = deque([])
        self.ohlc_6.maxlen = hma_period
        self.ema = deque([])
        self.ema.maxlen = ema_period + 1
        self.hma = deque([])
        self.hma.maxlen = 2

        # Load data
        self.load_60(curr_time, atr_period)
        self.load_6(curr_time, hma_period)
    
    def load_60(self, curr_time, n):
        """
        Load all 1hr ohlc data
        Calculate atr
        """
        # Make sure only the necessary number of bars is being grabbed
        n = self.ohlc_60.maxlen - len(self.ohlc_60) + 1
        data_raw = mt5.copy_rates_from(self.symbol, mt5.TIMEFRAME_H1, curr_time, n)

    def load_6(self, curr_time, n):
        """
        Load all 15 min ohlc data
        Calculate atr
        """
        # Make sure only the necessary number of bars is being grabbed
        n = self.ohlc_6.maxlen - len(self.ohlc_6) + 1
        data_raw = mt5.copy_rates_from(self.symbol, mt5.TIMEFRAME_M6, curr_time, n)
    
    
