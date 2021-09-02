import pandas as pd
from datetime import datetime
import MetaTrader5 as mt5

VERSION = """
          V 0.01
          Places stops
          Trails open orders by .25 * atr (1hr) above/below HMA 55
          """

if __name__ == "__main__":
    print(f"Begin Trade Follower \r\n{VERSION}")