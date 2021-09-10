import pandas as pd
c = ('fuck', 'shit', 'bitch', 'fu')
v = [
    (1,5,1,5),
    (2,2,2),
    (3,3,3)
]

d = pd.DataFrame(v, columns=c)

print(d['fu'])