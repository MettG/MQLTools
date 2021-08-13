"""
    Entry objects control entries for mt5
    Given a symbol, a direction, and a type, enter a new position

    ===Types===
        > Breakout
            Stop is low/high + spread
            Take is x2 stop
            Run until ttc cross over
        
        > Trend
            Stop is 1.5 * atr (1hr)
            Take is 1 * atr (1hr)
            Run if take hit and until ttc cross over

"""

class Entry:
    def __init__(self, symbol, direction, risk, type_of_trade='trend'):
        self.symbol = symbol
        self.direction = direction
        self.risk = risk
        self.type = type_of_trade

    def get_margin(self):
        """
            Reach out via Connection class to get current available margin 
        """
        if len(self.symbol) == 6: # Assumes currency pair
            # Reach out to meta trader
            # c = Connection(,)
        else:
            # Assumes tradovate, connect via api
            return

        