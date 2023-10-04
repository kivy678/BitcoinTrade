# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np

from binance import Client
from binance.exceptions import BinanceAPIException

from env import *

from util.bapi import *
from util.Logger import LOG
from util.utils import *

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Malgun Gothic'

#############################################################################

client = getClient()
assert client


# 현재 캔들 정보를 가져옵니다.
candles = client.get_klines(symbol='BTCUSDT',
                            interval='1h',
                            #limit=500,
                            startTime=kst_to_utc('20230927T170000'),
                            endTime=kst_to_utc('20231002T070000')
                            )


# 데이터 프레임 생성
df = pd.DataFrame(candles)
# 불필요한 컬럼 정리
df.drop(df.loc[:, 7:11], axis=1, inplace=True)
df.columns		= ['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

df['Open'] 		= df['Open'].astype(float)
df['High'] 		= df['High'].astype(float)
df['Low'] 		= df['Low'].astype(float)
df['Close'] 	= df['Close'].astype(float)
df['Volume'] 	= df['Volume'].astype(float)

df['OpenTime'] 	= df['OpenTime'].apply(utc_to_kst, args=(df['OpenTime'],))
df['CloseTime'] = df['CloseTime'].apply(utc_to_kst, args=(df['CloseTime'],))

df['previous_close'] = df['Close'].shift(1)
df.dropna(inplace=True)

df['close_diff'] = df['Close'] - df['previous_close']



# 가격과 볼륨 데이터 추출
price_and_volume = df[["close_diff", "Volume"]]

scaler = StandardScaler()
data_scaled = scaler.fit_transform(price_and_volume)


# 거래량에 가중치 부여
data_scaled[:, 1] *= 2  # 예시로 거래량에 2배의 가중치 부여

# Isolation Forest 모델 생성
model = IsolationForest(contamination=0.03)

# 모델 학습
model.fit(data_scaled)

# 이상치 탐지 (1이면 정상, -1이면 이상치)
predictions = model.predict(data_scaled)

# 이상치를 시각화
plt.figure(figsize=(12, 6))
plt.scatter(df.index, df["close_diff"], c=predictions, cmap='viridis', label="Price")
plt.scatter(df.index, df["Volume"], c=predictions, cmap='plasma', label="Volume")
plt.title("Bitcoin Price and Volume Outlier Detection")
plt.xlabel("Time")
plt.ylabel("Price and Volume")
plt.colorbar(label="Outlier")
plt.legend()
plt.show()

# 이상치를 포함하는 데이터 포인트 출력
rows_to_remove = []

outliers = df[predictions == -1]
for row in outliers.itertuples(index=True):
	
	if row.Open < row.Close:
		outliers.at[row.Index, 'Color'] = 1
		#rows_to_remove.append(row.Index)
	else:
		outliers.at[row.Index, 'Color'] = -1
		rows_to_remove.append(row.Index)


outliers = outliers.drop(rows_to_remove)

print("이상치 데이터 포인트:")
print(outliers)


print('Main End')

