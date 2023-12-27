# -*- coding:utf-8 -*-

#############################################################################

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from binance import Client
from binance.exceptions import BinanceAPIException
from util.utils import utc_to_kst

from env import *

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
    client = getClient()
    assert client

  
    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol='BTCUSDT',
                                interval=Client.KLINE_INTERVAL_1HOUR,
                                limit=15)


    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
  
    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)
    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']
  

    # 고점과 저점 찾기
    high    = df['High'].max()
    low     = df['Low'].min()

    # 피보나치 수준 계산
    fib_levels = [0, 0.236, 0.382, 0.5, 0.618, 1]
    
    price_diff = high - low
    fib_retracement_levels = {f'{level*100:.0f}%': high - price_diff * level for level in fib_levels}


    for level, price in fib_retracement_levels.items():
        print(f"Fibonacci Level {level}: {price:.2f}")


    df['CloseTime'] = df['CloseTime'].apply(utc_to_kst, args=('%Y-%m-%d:%H',))

    # 차트 생성
    plt.figure(figsize=(12, 8))

    # 캔들스틱 차트 그리기
    plt.plot(df['CloseTime'], df['Close'], label='BTCUSDT Price', color='blue')

    # 피보나치 수준을 가격 차트에 표시
    for level, price in fib_retracement_levels.items():
        plt.axhline(y=price, linestyle='--', label=f'Level {level} {price:.2f}')

    # 차트 제목 및 레이블 설정
    plt.title('BTCUSDT Price with Fibonacci Retracement Levels')
    plt.xlabel('Close Time')
    plt.ylabel('Price')

    # x축 날짜 형식 설정
    plt.gcf().autofmt_xdate()  # 날짜가 겹치지 않도록 자동 조정
    
    # 범례 표시
    plt.legend()

    # 차트 표시
    plt.show()


    closeClient(client)

    print('Main End')
