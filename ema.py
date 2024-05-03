# -*- coding:utf-8 -*-

#############################################################################

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import ta

from datetime import datetime
from binance import Client
from binance.exceptions import BinanceAPIException

from env import *

#############################################################################

KLINE_INTERVAL = Client.KLINE_INTERVAL_1HOUR

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


# EMA 계산
def calculate_emas(df, windows):
    for window in windows:
        ema = ta.trend.EMAIndicator(close=df['Close'], window=window)
        df[f'EMA{window}'] = ema.ema_indicator()
    return df


# 데이터 시각화
def plot_data(df, title):
    plt.figure(figsize=(14, 7))
    ax = plt.gca()
    for ema in [col for col in df.columns if 'EMA' in col]:
        plt.plot(df[ema], label=ema)
    plt.plot(df['Close'], label='Closing Price', color='black', alpha=0.3)
    plt.title(title)
    plt.legend()
    plt.show()


# 현재 캔들 정보를 가져옵니다.
def get_candle(clent, symbol):
    candles = client.get_klines(symbol=symbol,
                                interval=KLINE_INTERVAL,
                                limit=250)

    df = pd.DataFrame(candles)
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)

    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

    return df


if __name__ == '__main__':

    print('start main')

    client = getClient()
    assert client


    df = get_candle(client, 'BTCUSDT')

    windows = [20, 50, 100]  # 사용할 EMA 기간
    btc_ema = calculate_emas(df, windows)

    plot_data(btc_ema, 'Bitcoin EMA')

