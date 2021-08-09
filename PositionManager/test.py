import pandas as pd

my_dict = [
    {'high': 100, 'low':50},
    {'high': 102, 'low': 48},
    {'high': 103, 'low': 47}
]
data = pd.DataFrame(my_dict)
i = 0
while i < len(data):
    slic = data.iloc[[i, i+1, i+2]]
    highs = slic['high']
    lows = slic['low']
    print(highs.index[0])
    print(lows[2])
    new_dat = data.append(pd.DataFrame([200], index=[2], columns=['high']))
    print(new_dat)
    new_dat = new_dat.append(
        pd.DataFrame([100], index=[2], columns=['low'])
    )
    print(new_dat)
    new_dat = new_dat.append(
        pd.DataFrame([35], index=[1], columns=['low'])
    )
    print(new_dat)
    break