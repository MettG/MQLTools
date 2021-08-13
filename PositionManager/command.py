"""
    Send a given command to this class
    This command should be interpreted, and then carried out as instructed

    Tentative List of commands: (''-variable, ()-optional var)

        ----Order Entry (type is trend or breakout)----
            buy 'symbol' 'type' (quantity/risk)
            sell 'symbol' 'type' (quantity/risk)
        
        close (symbol) [Will attempt to close open position on symbol or all positions if none is given, by placing a stop order at the high/low of the previous bar]
        
"""
from PositionManager.entry import *


class Command:

    def convert_args(self):
        t = self.args[0]
        if len(self.args) > 3 and ( t == 'buy' or t == 'sell'):
            self.args[3] = int(self.args[2])
    
    def init_command(self):
        # Call the method per command
        t = self.args[0]
        if t == 'buy':
            risk = 0.02 if len(self.args) < 4 else self.args[3]
            Entry(self.args[1],0,risk,self.args[2])
        if t == 'sell':
            risk = 0.02 if len(self.args) < 4 else self.args[3]
            Entry(self.args[1],1,risk,self.args[2])
        
    def __init__(self, settings, command):
        # split command
        self.settings = settings
        self.args = command.split(" ")
        # convert relevant pieces
        self.convert_args()
        # call method relating to command
        self.init_command()

