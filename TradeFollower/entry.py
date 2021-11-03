import MetaTrader5 as mt5
from datetime import time, datetime
# ===============
# Order Entry Methods
# ===============

def get_lots(rate, balance, leverage, risk, stop_pips, isJPY= True, trades =2):
        """
        rate is CounterCurrency / AccountCurrency 
        Change mult to 10 if a JPY pair
        """
        max_lev = balance * leverage / 100000 / trades
        mult=1 if not isJPY else 100
        cash_risk = risk if risk >= 1 else balance * risk
        cash_risk /= trades
        per_pip = cash_risk / stop_pips
        size = per_pip * rate * mult
        size = 0.01 if size < 0.01 else size
        size = max_lev - 0.01 if size >= max_lev else size
        print(f"[ORDER] max_lev calculated: {max_lev} of {balance} {leverage}")
        print(f"[ORDER] size calculated: {size}")
        return round(size,2)

def confirm_result(result):
    try:
        if not result:
            raise Exception("[CRITICAL] No result when sending order.")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[CRITICAL] {result}")
            raise Exception(result.retcode)
        all_good = True
    except Exception as e:
        print(f"Error sending order request \n{e}")
        all_good = False

    return all_good

def build_request(vol, symbol, oType, sl, tp, price = 0, comment="", action=mt5.TRADE_ACTION_DEAL, position=0):
    digits = mt5.symbol_info(symbol).digits
    tp = round(tp, digits)
    sl = round(sl, digits)
    price = mt5.symbol_info_tick(symbol).ask if oType > 0 else mt5.symbol_info_tick(symbol).bid
    request = {
        "action": action,
        "symbol": symbol,
        "volume": vol,
        "type": oType,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 7,
        "magic": 0,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    } 
    if price != 0:
        request['type_filling'] = mt5.ORDER_FILLING_IOC
        del request['price']
    if position != 0 : request['position'] = position
    if comment != "" : request['comment'] = comment
    print(request)  
    # perform the check and display the result 'as is'
    result = mt5.order_send(request)
    return confirm_result(result)

def enter_new_order(dir, symbol, risk, data_keepers):
    print(f"Begin enter new order {dir} on {symbol}")
    # is percentage risk
    # call balance and calculate
    account_info = mt5.account_info()._asdict()
    if account_info == None:
        raise Exception(f"Error getting account info. {mt5.last_error()}")
    else:
        print(account_info)
    # Get rate of exchange for symbol
    if 'USD' in symbol:
        arr = symbol.split("USD")
        if arr[-1] == "":
            rate = 1
        else:
            # 1 / last market price
            rate = 1 / mt5.symbol_info(symbol).ask
            
    else:
        counter = symbol[3:]
        rate = mt5.symbol_info(counter+"USD")
        if rate == None: rate = 1 / mt5.symbol_info("USD"+counter).ask
        else: rate = rate.ask
    # print(f"rate found {rate}")
    
    dk = data_keepers[symbol]
    dk[0].set_functions(atr=20)
    ask = mt5.symbol_info(symbol).ask
    bid = mt5.symbol_info(symbol).bid
    dk[1].set_functions(hma=55, ema=8, std=20)
    stop = dk[1].get_stop(dir,ask,bid, dk[0].atr)
    stop_pips = (ask - stop) / mt5.symbol_info(symbol).point if dir == 0 else (stop - bid) / mt5.symbol_info(symbol).point
    lots = get_lots(rate,account_info['margin_free'] * .85,account_info['leverage'],risk,stop_pips,"JPY" in symbol)
    take = ask + dk[0].atr if dir == 0 else ask - dk[0].atr
    comment = ""
    if not build_request(lots,symbol,dir,stop,take, comment=comment):
        print("Order # 1 not placed.")
    else:
        time.sleep(2)
        if not build_request(lots,symbol,dir,stop,0.0, comment=comment):
            print("Order # 2 not placed.")
