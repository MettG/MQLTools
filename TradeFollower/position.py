import MetaTrader5 as mt5
import pandas as pd
from log import Log
from entry import build_request
from virtual_stop import manage_virtual
# =================
# Position Functions
# ================

def get_positions(positions):
    """
    Convert tuple of postions to panda dataframe
    """
    # display these positions as a table using pandas.DataFrame
    df=pd.DataFrame(list(positions),columns=positions[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.drop(['time_update', 'time_msc', 'time_update_msc', 'external_id'], axis=1, inplace=True)
    return df

def update_mean_position(oType, symbol, tickets, vol, open, hma, std, last_bar, manager=None):
    """
    Update mean reversion position
    When price hits opposite band, stop is placed at low/high
    When price closes beyond mean, move stop loss to max dist of mean +/- spread or open +/- 2 * spread
    """
    ask = mt5.symbol_info(symbol).ask
    bid = mt5.symbol_info(symbol).bid
    spread = ask - bid
    isUpdate = False
    if oType == 0:
        if last_bar['high'] >= hma + std:
            print("[POSITION] Mean position target hit.")
            Log("[POSITION] Mean position target hit.", symbol, oType, last_bar['low'], f'mean: {hma} upper: {hma+std}')
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,last_bar['low'])
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, last_bar['low'])
            isUpdate = True
        elif last_bar['close'] > hma:
            print("[POSITION] Mean position in profit")
            stop = open + 2 * spread
            if hma - spread > stop : stop = hma - spread
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, stop)
            isUpdate = True
    else:
        if last_bar['low'] <= hma - std:
            print("[POSITION] Mean position target hit.")
            Log("[POSITION] Mean position target hit.", symbol, oType, last_bar['high'], f'mean: {hma} lower: {hma-std}')
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,last_bar['high'])
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, last_bar['high'])
            isUpdate = True
        elif last_bar['close'] < hma:
            print("[POSITION] Mean position in profit")
            stop = open - 2 * spread
            if hma + spread < stop : stop = hma + spread
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, stop)
            isUpdate = True
    if isUpdate: print("[POSITION] Mean reversion position updated.")

def update_trend_position(oType, symbol, tickets, stop, open, atr60, hma, std, last_bar, manager=None):
    """
    Manage an open trend position,
    Trail price at band when on the positive side of the mean, else at .3 atr60 above/below band
    or price +/- atr15 if price is >= 2*atr15 away from mean
    Move price to break even if price is away from hma by 1 atr60
    """
    ask = mt5.symbol_info(symbol).ask
    bid = mt5.symbol_info(symbol).bid
    spread = ask - bid
    isUpdate = False

    if oType == 0:
        if ask >= hma + atr60 + std:
            # Price is far in profit
            print("[POSITION] Trend Position deep in profit.")
            new_stop = bid - atr60
            if new_stop < open + std or new_stop <= stop:
                print("[POSITION] Trend Buy Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is very far away from mean, updating stop to in profit.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
        elif ask - hma >= atr60:
            print("[POSITION] Trend Position, break even triggered as price is far from mean.")
            Log("[TREND POSITION] Break even triggered.", symbol, open, f"{stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,open + 2 * spread)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, open + 2 * spread)
            isUpdate = True
        elif ask > hma:
            print("[POSITION] Trend Postion, price is on positive side of mean.")
            stop_ok = True
            new_stop = hma - std
            reason = "Trailing Profitable move."
            if new_stop < open + std or new_stop <= stop:
                # Trail stop not applicable, test for break even if reversal bar
                o = last_bar['open']
                c = last_bar['close']
                l = last_bar['low']
                h = last_bar['high']
                new_stop = open + .2 * atr60
                if open - bid >= std and ( (o < c and o-l >= .4 * (h-l) and h - c < o - l) or (o > c and c - l >= .4 * (h-l) and h - o < c - l) ) and new_stop > stop:
                    print("[POSITION] Trend Postion, reversal bar detected, break even triggered.")
                    reason = "Emergency Break Even triggered."
                else:
                    stop_ok = False
            if not stop_ok:
                print("[POSITION] Trend Sell Position conditions not met for profit trail or emergency break even.")
                return
            Log("[TREND POSITION] Price is on positive side of mean.", symbol, open, reason, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
        else:
            print("[POSITION] Trend Position, price is on negative side of mean.")
            new_stop = hma - std - .3 * atr60
            if new_stop <= stop or new_stop <= open:
                print("[POSITION] Trend Buy Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is on negative side of mean.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol, new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
    else:
        if bid <= hma - atr60 -std:
            # Price is far in profit
            print("[POSITION] Trend Position deep in profit.")
            new_stop = ask + atr60
            if new_stop > open - std or new_stop >= stop:
                print("[POSITION] Trend Sell Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is very far away from mean, updating stop to in profit.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True
        elif hma - bid >= atr60:
            print("[POSITION] Trend Position, break even triggered as price is far from mean.")
            Log("[TREND POSITION] Moving stop to break even.", symbol, open, f"{stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,open - 2 * spread)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, open - 2 * spread)
            isUpdate = True
        elif bid < hma:
            print("[POSITION] Trend Postion, price is on positive side of mean.")
            stop_ok = True
            new_stop = hma + std
            reason = "Trailing Profitable move."
            if new_stop > open - std or new_stop >= stop:
                # Trail stop not applicable, test for break even if reversal bar
                o = last_bar['open']
                c = last_bar['close']
                l = last_bar['low']
                h = last_bar['high']
                new_stop = open - .2 * atr60
                if open - bid >= std and ( (o < c and h - c >= .4 * (h-l) and o - l < h - c) or (o > c and h - o >= .4 * (h-l) and c - l < h - o) ) and new_stop < stop:
                    print("[POSITION] Trend Postion, reversal bar detected, break even triggered.")
                    reason = "Emergency Break Even triggered."
                else:
                    stop_ok = False
            if not stop_ok:
                print("[POSITION] Trend Sell Position conditions not met for profit trail or emergency break even.")
                return
            Log("[TREND POSITION] Price is on positive side of mean.", symbol, open, reason, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol,hma + std)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, hma + std)
            isUpdate = True
        else:
            print("[POSITION] Trend Position, price is on negative side of mean.")
            new_stop = hma + std + .3 * atr60
            if new_stop >= stop or new_stop >= open:
                print("[POSITION] Trend Sell Position not far enough in profit for stop update.")
                return
            Log("[TREND POSITION] Price is on negative side of mean.", symbol, open, f"{stop} -> {new_stop}")
            manage_virtual(manager,int(tickets.iloc[0]), oType, symbol, new_stop)
            if len(tickets) > 1:
                manage_virtual(manager,int(tickets.iloc[1]), oType, symbol, new_stop)
            isUpdate = True

    if isUpdate: print("[POSITION] Trend position updating successfully.")

    
def update_runner_position(oType, symbol, ticket, vol, open, trail_dist, hma, manager=None):
    """
        Update runner type of positions,
        Follows hma by .25 atr
        close when price closes over HMA
    """
    print(f"[MANAGER] Runner Position to update:\r\n{ticket}:{mt5.positions_get(ticket=ticket)}")
    isUpdate = True
    if oType == 0:
        price = mt5.symbol_info_tick(symbol).ask
        if price < hma:
            # close_res = build_request(vol,symbol,1,0.0,0.0,price=open,action=mt5.TRADE_ACTION_DEAL,position=ticket)
            close_res = mt5.Close(symbol, ticket=ticket)
            if not close_res:
                Log("[Critical] Error when closing runner", symbol, oType, price, f'mean:{hma}')
                isUpdate = False
                
            else:
                print("[POSITION] Buy runner closed.")
        else:
            new_stop = hma - trail_dist if hma - trail_dist > open + trail_dist else open + trail_dist
            update_res = build_request(vol,symbol,1,new_stop,0.0, action=mt5.TRADE_ACTION_SLTP, position=ticket, comment="runner")
            if not update_res:
                Log("[Critical] Error when updating runner", symbol, oType, new_stop, f'mean:{hma}', f'newstop:{new_stop}')
                isUpdate = False
                # Add Virtual Stop
                manage_virtual(manager,ticket,oType,symbol,new_stop)
            else:
                print("[POSITION] Buy runner updated.")
    else:
        price = mt5.symbol_info_tick(symbol).bid
        if price < hma:
            # close_res = build_request(vol,symbol,0,0.0,0.0,price=open,action=mt5.TRADE_ACTION_DEAL,position=ticket)
            close_res = mt5.Close(symbol, ticket=ticket)
            if not close_res:
                Log("[Critical] Error when closing runner", symbol, oType, price, f'mean:{hma}')
                isUpdate = False
            else:
                print("[POSITION] Sell runner closed.")
        else:
            new_stop = hma +trail_dist if hma + trail_dist < open - trail_dist else open - trail_dist
            update_res = build_request(vol,symbol,0,new_stop,0.0,action=mt5.TRADE_ACTION_SLTP, position=ticket, comment="runner")
            if not update_res:
                Log("[Critical] Error when updating runner", symbol, oType, price, f'mean:{hma}', f'newstop:{new_stop}')
                isUpdate = False
                # Add Virtual Stop
                manage_virtual(manager,ticket,oType,symbol,new_stop)
            else:
                print("[POSITION] Sell runner updated.")
    
    if isUpdate: print("[POSITION] Runner updated or closed successfully.")


def set_profit_position(vol, symbol, oType, ticket_to_close, ticket_to_even, break_dist):
    price = mt5.symbol_info_tick(symbol).ask if oType > 0 else mt5.symbol_info_tick(symbol).bid
    sl = price + break_dist if oType > 0 else price - break_dist
    closeType = 0 if oType > 0 else 1
    close_res = build_request(vol,symbol,closeType,0,0,action=mt5.TRADE_ACTION_DEAL,position=ticket_to_close)
    even_res = build_request(vol,symbol,oType,sl,0,action=mt5.TRADE_ACTION_SLTP, position=ticket_to_even, comment="runner")
    isError = False
    if not close_res:
        Log("[CRITICAL] Error when closing for 1st profit", symbol, oType, price)
        isError = True
    if not even_res:
        Log("[CRITICAL] Error when updating break even", symbol, oType, price)
        isError = True
    if not isError: print("[POSITION] Position successfull set to profit type.")
 

def extract_symbols(positions):
    arr = []
    for sym in positions['symbol']:
        if sym not in arr: arr.append(sym)
    return arr