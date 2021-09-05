import pandas as pd
from datetime import datetime
from PositionManager.data_handler import DataHandler
import MetaTrader5 as mt5


VERSION = """
    Version 0.01
    Basic open position management using hma 55 and ema 8
    Automatically set stops
    =====RULES========= (atr is 1hr atr 20)
    Buy >
        Move position to break even (+.2 * atr) if ema is > open + .8 * atr
        Once position is broke even, trail price at low - 1.5 * spread if ema < hma
    Sell >
        Move position to break even (-.2 * atr) if ema < open - .8 * atr
        Once position is broke even, trail price at high + 1.5 * spread if ema > hma

    Everything is calculated using 6 min data for now, except for the atr which is 1hr data

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
    def __init__(self, positions, settings):
        self.positions = get_positions(positions)
        self.symbols = self.extract_symbols()
        self.symbol_dict = {} # Dictionary of datahandlers
        self.settings = settings # Holds settings data like periods for indicators

    def gather_data(self):
        """
        Build the datahandlers given the symbols extracted from open positions

        """
        # Check if has datahandlers, check if has positions for datahandlers. Delete or add where necessary
        # Should only have datahandlers for open positions
        for sym in self.symbols:
            exists = sym in self.symbol_dict
            
            if not exists:
                d = DataHandler(sym) # Update this to include settings
                d.calculate()
                # Add the new data handler
                self.symbol_dict[sym] = d
            else:
                dh = self.symbol_dict[sym]
                dh.validated = True
                dh.calculate()


    def manage_open_positions(self):
        """
            After gathering the data, manage the open positions.
            Each position's datahandler is unvalidated after management
            deletes any validated datahandlers, since no open position needs its data
        """
        for pos in self.positions:
            if not pos.symbol in self.symbol_dict:
                # This should never happen
                raise Exception("Trying to manage a position for which there is no datahandler is gather data called first?")
            d = self.symbol_dict[pos.symbol]
            d.validated = False
            # Check what stage the position is in
            # New : no stops
            if pos.stop == 0:
                # No stop, calculate stop and update position
                newStop = d.calculate_stop(pos.type, pos.openTime, pos.open)
                
                pos.stop = newStop
                pos.init_stop = newStop

            else:
                # Active : stops have been placed, trail hma +/- .25 * atr
                # Profit : target (.85 * atr) has been reached, watch for exit signal
                
                # Check if Target reached
                if d.target_hit(pos.openTime,0.85) and d.exit_signal():
                    # Call method to send a close position mt5 request
                    pos.close()
                    return
                newStop = d.calculate_trail_stop(pos.type, pos.init_stop)
                
                pos.stop = newStop

            pos.update()
                
                



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
            
            


