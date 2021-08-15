import pandas as pd

my_dict = [
    {'high': 100, 'low':50},
    {'high': 102, 'low': 48},
    {'high': 103, 'low': 47}
]
data = pd.DataFrame(my_dict)
i = 0
print(data.iloc[::-1])