import MetaTrader5 as mt5

class VirtualStop:
    """
    Class for holding a virtual stop.
    close position when prices closes beyond the stop
    """
    def __init__(self, ticket, oType, price):
        self.type = oType
        self.price = price
        self.id = int(ticket)
    def check_close(self,symbol):
        print(f"[VIRTUAL STOP] Checking stop on {'buy' if self.type == 0 else 'sell'} {self.id} @ {self.price}")
        return (self.type == 0 and mt5.symbol_info_tick(symbol).bid < self.price) or (self.type == 1 and mt5.symbol_info_tick(symbol).ask > self.price)
    def __str__(self) -> str:
        o = "sell" if self.type == 1 else "buy"
        return f"{o} pos {self.id}, virtual @ {self.price}"

class VirtualManager:
    """
    Create and update virtual stops
    Hold virtuals in a dictionary of symbols
    """
    def __init__(self):
        self.virtuals = {}
    def add(self, ticket, oType, symbol, price):
        new_stop = VirtualStop(ticket, oType,price)
        if symbol in self.virtuals:
            new_arr = []
            for stop in self.virtuals[symbol]:
                # Ensure stop is further in profit than previous stop, else don't update
                if (oType == 0 and price < stop.price) or (oType == 1 and price > stop.price):
                    print("[VIRTUAL MANAGER] New stop would be less in profit than current.")
                    return
                new_arr.append(new_stop)
            self.virtuals[symbol] = new_arr
            print(f"[VIRTUAL MANAGER] Virtuals updated on {symbol}")
        else:
            self.virtuals[symbol] = [new_stop]
            print(f"[VIRTUAL MANAGER] New virtual added on {symbol}")

    def update(self):
        """
        Call every so often, check if virtual stops are triggered or not
        """
        for sym in self.virtuals:
            for stop in self.virtuals[sym]:
                error = False
                print("[VIRTUAL STOP]", stop)
                if stop.check_close(sym):
                    if mt5.Close(sym,ticket=stop.id):
                        print(f"[VIRTUAL STOP] Position on {sym} closed successfully.")
                    else:
                        print(f"[CRITICAL] Position on {sym} with virtual stop failed to close. {mt5.last_error()}")
                        error = True

                position=mt5.positions_get(ticket=stop.id)
                if error:
                    print(f"[VIRTUAL STOP] Error closing position {position}")
                if position == None or not position:
                    print(f"[VIRTUAL STOP] Position {stop} no longer exists.")
                    del stop
                    

    