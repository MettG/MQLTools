from datetime import datetime
# =================
# Log Functions
# ================

class Log:
    """
        Takes care of all logging, takes a list of args, to be displayed in order
    """
    def __init__(self, *args):
        """
        First argument is the message, second is the symbol, the rest are relevant information
        """
        utc_from = datetime.utcnow()
        s = args[0]
        sym = args[1]
        val = f"{utc_from}: {s} \n{args[2:]}"
        print(val)
        with open(f'./logs/{sym}_log.txt', 'a') as f:
            f.write("\r\n")
            f.write(val)
            f.write("\r\n")