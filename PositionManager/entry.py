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