# -*- coding:utf-8 -*-

#############################################################################

import pandas as pd
import numpy as np

from binance import Client
from binance.exceptions import BinanceAPIException

from env import *

#############################################################################


if __name__ == '__main__':
    client = getClient()
    assert client

    #server_time_sync(client)

  
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



    closeClient(client)

    print('Main End')
