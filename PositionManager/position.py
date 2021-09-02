import pandas as pd
class Position:
    def __init__(self, ticket, openTime, orderType, volume, open, stop, take, price, profit, symbol):
        self.ticket = ticket
        self.openTime = openTime
        self.type = orderType
        self.volume = volume
        self.open = open
        self.stop = stop
        self.init_stop = stop # Special stop that signifies the furthest a stop can be moved
        self.virtualStop = stop # Unused feature
        self.take = take
        self.virtualTake = take # Unused feature
        self.market_price = price
        self.profit = profit
        self.symbol = symbol
        self.info = None # Unused feature, for saving information about a position
    
    def update(self):
        # Send a request to mt5 to update the order with this positions ticket, with this positions variables
        pass
    def close(self):
        # Send a request to mt5 to close the position with this ticket
        pass

def get_positions(raws):
    """
    Given a named tuple of all positions, build them into pandas data frame objects, and then into Position objects and return them in a list
    """
    df=pd.DataFrame(list(raws),columns=raws[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
    arr = []
    for _, row in df.iterrows():
        arr.append(new_position(row))

def new_position(df):
    """
    Build and return a new Position object given a convered pd df
    """
    return Position(
        df['ticket'], df['time'], df['type'],
        df['volume'], df['price_open'], df['sl'],
        df['tp'],df['price_current'],df['profit'], df['symbol']
    )