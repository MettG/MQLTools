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
        self.positions = positions
        self.symbols = self.extract_symbols()
        self.symbol_data = None

    def gather_data(raw):
        """
        After passing the symbols and pulling the correct data, format it and save it
        """
        
