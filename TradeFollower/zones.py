import pandas as pd

# Given a df of ohlc, determine if bar is a hammer candle
def is_hammer(ohlc):
    full = ohlc['high'] - ohlc['low']
    a = ohlc['close'] if ohlc['close'] > ohlc['open'] else ohlc['open']
    b = ohlc['close'] if ohlc['close'] < ohlc['open'] else ohlc['open']
    body = a - b
    upper = ohlc['high'] - a
    lower = b - ohlc['low']
    return lower >= full * .5 and lower > body and lower > upper

# Given a df of ohlc, determine if bar is a pin candle
def is_pin(ohlc):
    full = ohlc['high'] - ohlc['low']
    a = ohlc['close'] if ohlc['close'] > ohlc['open'] else ohlc['open']
    b = ohlc['close'] if ohlc['close'] < ohlc['open'] else ohlc['open']
    body = a - b
    upper = ohlc['high'] - a
    lower = b - ohlc['low']
    return upper >= full * .5 and upper > body and upper > upper
    
class Zone:
    def __init__(self, price, atr):
        self.anchor = price
        zone = atr
        self.upper = price + zone
        self.lower = price - zone
        self.expire_dist = 2 * atr
    
    def in_zone(self, price):
        """
        Return true if price is within the bounds of the zone
        """
        return price >= self.lower and price <= self.upper
    
    def above_zone(self,price):
        """
        Return true if price above the upper zone bound
        """
        return price > self.upper
    
    def below_zone(self,price):
        """
        Return true if price below the lower zone bound
        """
        return price < self.lower 
    
    def zone_expired(self, close):
        """
        Return true if close price is far away from zone
        """
        return abs(close - self.anchor) >= self.expire_dist

class DemandZone (Zone):
    def __init__(self, price, atr):
        Zone.__init__(price,atr)
    
    def is_entry(self, ohlc):
        """
        Given the last bar, a pandas DF of ohlc, determine if price is an entry or not.
        An entry is determined by a hammer candle whose high above zone and low is in zone.
        If zone is expired, it will automatically delete itself.
        """
        close = ohlc['close']
        if self.zone_expired(close):
            del self
            return False
        return (( self.in_zone(ohlc['low']) and self.above_zone(ohlc['high'])) or self.in_zone(close)) and is_hammer(ohlc)

class SupplyZone (Zone):
    def __init__(self,price,atr):
        Zone.__init__(price,atr)
    
    def is_entry(self, ohlc):
        """
        Given the last bar, a pandas DF of ohlc, determine if price is an entry or not.
        An entry is determined by a pin candles whose low is below zone and high is in zone.
        If zone is expired, it will automatically delete itself.
        """
        close = ohlc['close']
        if self.zone_expired(close):
            del self
            return False
        return ( (self.below_zone(ohlc['low']) and self.in_zone(ohlc['high'])) or self.in_zone(close)) and is_pin(ohlc)


def is_buy(ohlc):
    """
    Given an ohlc bar, determine if it is a buy bar or sell bar
    """
    return ohlc['open'] < ohlc['close']


# Given a direction (1:buy -1:sell) and bars, try to construct a new zone
# Supply zones need 3 cons red bars
# Demand zones need 3 cons green bars
# zone anchor is mid point of the 4th bar in history after the above is discovered
def try_build_zone(dir, ohlc: pd.DataFrame, atr):
    new_zone = None
    anchor = 0.0 # Anchor for the zone
    # Loop through ohlc
    for i, _ in ohlc.iterrows():
        if i > len(ohlc) - 3: break
        # Find 3 consec bars
        if dir == 1:
            # buy
            if is_buy(ohlc.iloc[i]) and is_buy(ohlc.iloc[i+1]) and is_buy(ohlc.iloc[i+2]):
                # Demand zone at i+3
                anchor = (ohlc.iloc[i+3]['high'] + ohlc.iloc[i+3]['low']) / 2
        else:
            # sell
            if not is_buy(ohlc.iloc[i]) and not is_buy(ohlc.iloc[i+1]) and not is_buy(ohlc.iloc[i+2]):
                # Supply zone at i+3
                anchor = (ohlc.iloc[i+3]['high'] + ohlc.iloc[i+3]['low']) / 2
        # Use mid point as anchor for new zone
    if anchor == 0:
        print("[ZONE ENTRY] No Zone discovered.")
        return new_zone
    new_zone = DemandZone(anchor,atr) if dir == 1 else SupplyZone(anchor, atr)
    print("[ZONE ENTRY] New Zone found @",new_zone.anchor, dir)
    return new_zone

# TO DO

# ADD a recursive entry type, where it will look to enter up to twice as long as the zone doesn't expire

class ZoneEntry:
    """
    Holds logic for each zone entry. Update every new bar and enter order accordingly based on update return bool.
    """
    def __init__(self, dir, recursive=False):
        self.zone = None
        self.entry_dir = dir # When this is either 1 or -1, begin exercising entry logic
        self.recursing = recursive
    
    def update(self, ohlc: pd.DataFrame, atr) -> bool:
        """
        Update the Entry with the bars (ohlc pandas df)
        A higher number of bars will cause the manager to look further back in time for a zone, this could lead to some issues
        Returns true if entry is detected, false other wise.
        Also if there is no entry (entry_dir == 0) will just return false
        """
        if self.entry_dir == 0: return False

        if self.zone == None:
            self.zone == try_build_zone(self.entry_dir, ohlc, atr)

        if self.zone == None:
            # No zone found, still keep trying to find zone
            return False
        return self.zone.is_entry(ohlc.iloc[0])

class ZoneManager:
    def __init__(self):
        self.zones = {}

    def update(self, symbol, ohlc, atr):
        """
        Pass in the symbol and the bars from its data keep and the current atr to update zones
        Returns true if the zone for the given symbol signals an entry, false otherwise
        """
        if symbol in self.zones:
            return self.zones[symbol].update(ohlc,atr)
    
    def new_zone(self, symbol, dir, is_recursive=False):
        """
        Create a new zone entry, given the symbol and the direction. A recursive entry continously builds new zones and looks for entries until:
        Two entries have been created or a zone expires.
        """
        self.zones[symbol] = ZoneEntry(dir, is_recursive)
    
    def symbols(self):
        """
        Return all symbols of the existing zone entries
        """
        return list(self.zones.keys())
    
    def delete_zone(self, symbol):
        """
        Force a zone to delete on the given symbol
        """
        if symbol in self.zones:
            del self.zones[symbol]
            print(f"[ZONE MANAGER] zone on {symbol} deleted successfully.")
