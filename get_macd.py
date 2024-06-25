# -*- coding:utf-8 -*-

#############################################################################

import ta
import pandas as pd
import numpy as np

import matplotlib.pyplot as plt

from util.utils import utc_to_kst
from binance import Client
from binance.exceptions import BinanceAPIException

from env import *

KLINE_INTERVAL = Client.KLINE_INTERVAL_15MINUTE
from binance.helpers import round_step_size

#############################################################################


def getClient():
    try:
        return Client(BINANCE_ACCESS, BINANCE_SECRET, {"verify": True, "timeout": 20})
    except BinanceAPIException as e:
        print(e)
        return False


def closeClient(client):
    try:
        client.close_connection()
    except BinanceAPIException as e:
        print(e)
        return False


if __name__ == '__main__':

    print('start main')

    client = getClient()
    assert client


    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol='BTCUSDT',
                                interval=Client.KLINE_INTERVAL_1HOUR,
                                limit=200)


    # 데이터 프레임 생성 및 불필요한 컬럼 정리
    df = pd.DataFrame(candles)
    df.drop(df.loc[:, 0:4], axis=1, inplace=True)
    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

    print(df)

    # ta 라이브러리를 사용하여 MACD 계산
    df['MACD'] = ta.trend.macd(df['Close'])
    df['Signal'] = ta.trend.macd_signal(df['Close'])
    df['Diff'] = ta.trend.macd_diff(df['Close'])

    # MACD와 신호선 시각화
    plt.figure(figsize=(14, 7))
    plt.plot(df.index, df['MACD'], label='MACD', color = 'red')
    plt.plot(df.index, df['Signal'], label='Signal Line', color='blue')
    plt.bar(df.index, df['Diff'], label='MACD Histogram', color='green', alpha=0.5)
    plt.legend(loc='upper left')
    plt.title('MACD, Signal Line, and MACD Histogram')
    plt.show()


    closeClient(client)

    print('Main End')
