"""
Handle and hold all data for the manager

#### TO DO #######
1. Test all values


"""
from os import read
import MetaTrader5 as mt5
from collections import deque
from datetime import datetime
import pandas as pd
from PositionManager.utils import *

class DataPiece:
    def __init__(self, timeOf, val):
        self.time = timeOf
        self.value = val

class DataHandler:

    def calculate(self):
        """
            Force Load all data, calculate indicators, must be called during the opening second of the hour and six minute bar
            Updates .isReady flag depending on if a new calculation was had or not
            If not .isReady then no new data is available
        """
        curr_time = datetime.utcnow()
        ready = False # Used to see if new information is available
        self.validated = True # Used to see if position still exists, otherwise, dipose of the datahandler

        # load 60 if time is 60
        if curr_time.total_seconds() % ( 60 * 60) == 0: 
            self.load_60(curr_time, self.atr_period)
            self.recalculate("atr")
            print("1 hr data loaded and atr calculated.")
        if curr_time.total_seconds() % (60 * 6) == 0:
            self.load_6(curr_time, self.hma_period)
            self.recalculate("ema", "hma")
            print("60 min data loaded and ema/hma recalculated.")
            ready = True
        self.isReady = ready
        if not ready:
            print("New data not available/loaded.")
        

    def recalculate(self, *args):
        if "ema" in args:
            # Update ema 9 deque
            self.ema.appendleft(
                calculate_ema(list(self.ohlc_6['close']), self.ema_period)
            )
    
        if "hma" in args:
            # Update hma 55 deque
            self.hma.appendleft(
                HMA(self.ohlc_6['close'], self.hma_period).iloc[-1]
            )

        if "atr" in args:
            # Update atr
            self.atr = calculate_atr(
                calculate_tr(self.ohlc_60),
                self.atr_period
            )
                

    def __init__(self, symbol, hma_period=55, ema_period=9, atr_period=20):
        # Used for stops
        self.ohlc_60 = deque([],maxlen=atr_period+1)
        self.hma_period = hma_period
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr = 0
        self.symbol = symbol

        # Used for exit strategy
        self.ohlc_6 = deque([], maxlen=hma_period+2)
        self.ema = deque([], maxlen=2)
        self.hma = deque([], maxlen=2)

        # Load data
        self.calculate()
        self.isReady = False # Track if all data is ready
        self.validated = True # Track if open position or not (do we need this data handler?)
    
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
            if self.ohlc_60[0].index != data.iloc[[-1]].index:
                self.ohlc_60.appendleft(data.iloc[[-1]])
            else:
                print("ohlc_60 data not ready for update.")
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
            if self.ohlc_6[0].index != data.iloc[[-1]].index:
                self.ohlc_6.appendleft(data.iloc[[-1]])
            else:
                print("ohlc_6 data not ready for update.")

    def calculate_stop(self,posType,openTime,openPrice):
        # Look ema period back, starting at openTime, for the lowest/highest, choose the smallest distance between that
        # and 1 atr from openPrice
        anchor = openPrice
        j = 0
        for i, val in self.ohlc_6.iteritems():
            if i > openTime: continue
            j+=1
            newAnchor = val['low'] if posType == 0 else val['high']
            if (posType == 0 and newAnchor < anchor) or (posType == 1 and newAnchor > anchor):
                anchor = newAnchor
            if j > self.ema_period: break
        if abs(openPrice - anchor) < self.atr:
            return anchor
        else:
            return (openPrice - self.atr if posType == 0 else openPrice + self.atr)
    
    def calculate_trail_stop(self, posType, initStop):
        dist = self.atr * .25
        stop = self.hma[0] - dist if posType == 0 else self.hma[0] + dist
        stop = stop if (posType == 0 and stop > initStop) or (posType == 1 and stop < initStop) else initStop
        return stop
        
if __name__ == "__main__":
    # If not an import, assume testing
    if not mt5.initialize():
        print("mt5 failed to init")
        quit()
    
    # Create a data handler
    d = DataHandler("EURUSD", datetime.utcnow())



    
