import pandas as pd

class TrueTrendChannel:
    def __init__(self, period, timeframe):
        """
            Period is how many swings to use for ema average
            timeframe is in minutes
        """
        self.high = pd.DataFrame(columns=['value'], index=[pd.DatetimeIndex])
        self.low = pd.DataFrame(columns=['value'], index=[pd.DatetimeIndex])
        self.swings = pd.DataFrame(columns=['high', 'low'], index=[pd.DatetimeIndex])
        self.len = period
        self.tf = timeframe

    def init_swing_data(self, new_swing, label='high'):
        """
            Where new swing is (index, swing value),
            Fill out all swing indexes until swings are as long as len + 1 for ema calculation
        """
        self.swings = self.swings.append(pd.DataFrame([new_swing[1]], index=[new_swing[0]], columns=[label]))
        while len(self.swings) < self.len + 1:
            self.swings.append(pd.DataFrame)

    
    # Boot up indicator
    def load(self, data):
        """
        Requires data of ohlc type, enough to fill up the given period worth of swing data
        """
        # Raw swings, (index, value)
        high_raw = None
        low_raw = None
        # Fill swings until we have enough
        index = 0
        while True:
            swingFound = "none" # None, Low, High, Both
            while True:
                if swingFound != "none": break
                slic = data.iloc[[index, index+1, index+2]]
                highs = slic['high']
                lows = slic['low']
                if highs[0] < highs[1] and highs[1] >= highs[2]:
                    high_raw = (highs.index[1], highs[1])
                    swingFound = "high"
                if lows[0] > lows[1] and lows[1] <= lows[2]:
                    low_raw = (lows.index[1], lows[1])
                    swingFound = "both" if swingFound == "high" else "low"
                index+=1
            # Check if new swing high or low was found
            if swingFound == "high":
                # If first swing found, use to fill the rest of the swing indexes
                if len(self.swings) == 0:
                    





            




    # Check if swing low or not
    def check_swing_low(self, low, lowPast, lowAncient):
        return False
    # Check if swing high or not
    def check_swing_high(self, high, highPast, highAncient):
        return False

    def update(self, data):
        """
        Update indicator with new bar data
        """
        pass
    
    