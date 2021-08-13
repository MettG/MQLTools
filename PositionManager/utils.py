"""
    House functions like ATR, EMA, and HMA here
"""
import pandas as pd
import numpy as np

# HMA= WMA(2*WMA(n/2) − WMA(n)),sqrt(n))
def WMA(data, period):
       return data.rolling(period).apply(lambda x: ((np.arange(period)+1)*x).sum()/(np.arange(period)+1).sum(), raw=True)

def HMA(data, period):
       return WMA(WMA(data, period//2).multiply(2).sub(WMA(data, period)), int(np.sqrt(period)))

def calculate_ema(data, period, smoothing=2):
    """
    Calculate EMA of a given series
    """
    ema = [sum(data[:period])/period]
    for d in data[period:]:
        ema.append((d * (smoothing / (1 + period))) + ema[-1] * (1 - (smoothing / (1 + period))))
    return ema[-1]

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
