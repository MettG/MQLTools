import pandas as pd
from datetime import datetime
#import MetaTrader5 as mt5
import pyautogui
from multiprocessing import Process, Pipe

 # always returns "OK"
# pyautogui.confirm('Asks OK or Cancel')  # returns "OK" or "Cancel"

# pyautogui.password('Enter password')  # returns string or None

VERSION = """
          V 0.01
          Places stops
          Trails open orders by .25 * atr (1hr) above/below HMA 55
          """

class Command:
    def __init__(self, title):
        self.isReady = False
        self.title = title
    
    def set_command_ready(self, title):
        self.title = title
        self.isReady = True

def com_function(conn):
    com_raw = pyautogui.prompt('Enter Command')  # returns string or None
    print(com_raw)
    conn.send([com_raw])

if __name__ == "__main__":
    print(f"Begin Trade Follower \r\n{VERSION}")
    par_con, chi_con = Pipe()

    com_process = Process(target=com_function, args=(chi_con))
    com_process.start()

    
