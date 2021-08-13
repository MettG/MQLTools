import pandas as pd
from datetime import datetime
import MetaTrader5 as mt5


VERSION = """
    Version 0.01
    Basic open position management using hma and ema (55 period)
    Automatically set stops
    =====RULES========= (atr is 1hr atr 20)
    Buy >
        Move position to break even (+.2 * atr) once price has closed above ema and ema is 1 atr above hma and the position's open price
        Once take profit (1*atr) is hit, close position once close is < hma
    Sell >
        Move position to break even (-.2 * atr) once price has closed above ema and ema is 1 atr below hma and the position's open price
        Once take profit (1*atr) is hit, close position once close > hma

    Everything is calculated using 15 min data for now, except for the atr which is 1hr data

"""

def get_positions(positions):
    """
    Convert tuple of postions to panda dataframe
    """
    # display these positions as a table using pandas.DataFrame
    df=pd.DataFrame(list(positions),columns=positions[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
    return df

class Manager:
    """
    Takes the positions and the symbol data and creates actions:
    Update Trail Stop, update Exit Stop
    """
    def extract_symbols(self):
        arr = []
        for pos in self.positions:
            if pos.symbol not in arr: arr.append(pos.symbol)
    def __init__(self, positions):
        self.positions = get_positions(positions)
        self.symbols = self.extract_symbols()
        self.symbol_data = None

    def gather_data(raw):
        """
        After passing the symbols and pulling the correct data, format it and save it
        """
        

if __name__ == "__main__":
    # Script is running in standalone, meaning that only the manager is running
    if not mt5.initialize():
        print("init failed.")
        mt5.shutdown()

    # request connection status and parameters
    print(mt5.terminal_info())
    # get data on MetaTrader 5 version
    print(mt5.version())
    print("Position Manager online")
    print(VERSION)
    while True:
        utc_from = datetime.utcnow()
        positions = mt5.positions_get()
        if positions==None:
            # Give all the formatted positions to the manager
            m = Manager(get_positions)
            
            


