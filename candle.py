# -*- coding:utf-8 -*-

#############################################################################

import pandas as pd
from pandas import Series, DataFrame
import numpy as np

import pprint
import win32api
import time
from datetime import datetime

from binance import Client
from binance.exceptions import BinanceAPIException

from env import KEY, SECRET

#############################################################################


def getClient():
    try:
        return Client(KEY, SECRET, {"verify": True, "timeout": 20})
    except BinanceAPIException as e:
        print(e)
        return False


def closeClient(client):
    try:
        client.close_connection()
    except BinanceAPIException as e:
        print(e)
        return False


def server_time_sync(client):
    try:
        server_time= client.get_server_time()
    
        gmtime = time.gmtime(int((server_time["serverTime"])/1000))
        win32api.SetSystemTime(gmtime[0],
                                gmtime[1],
                                0,
                                gmtime[2],
                                gmtime[3],
                                gmtime[4],
                                gmtime[5],
                                0)

    except BinanceAPIException as e:
        print(e)
        return False



if __name__ == '__main__':
    client = getClient()
    assert client

    server_time_sync(client)


    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol='BTCUSDT',
                                interval=Client.KLINE_INTERVAL_15MINUTE,
                                limit=5)

    for i in candles:
        print(i)


    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
    df.index.name = 'id'

    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']


    # 가격이 올라야 양봉이다. 즉 open < close 이다.
    for i in range(5):
        if df.loc[i, 'Open'] < df.loc[i, 'Close']:
            df.loc[i, 'Color'] = 1
        else:
            df.loc[i, 'Color'] = -1

    print(df)


    closeClient(client)

    print('Main End')
