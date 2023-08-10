# -*- coding:utf-8 -*-

#############################################################################

import pandas as pd
import numpy as np

import pprint
import win32api
import time
from datetime import datetime

from binance import Client
from binance.exceptions import BinanceAPIException

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
                                limit=250)


    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
    df.index.name = 'id'


    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)
    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']


    # diff 함수를 이용하여 컬럼의 차를 구한다.
    delta   = df['Close'].diff()


    # 상승폭, 하락폭 계산
    gain    = delta.where(delta > 0, 0)
    loss    = delta.where(delta < 0, 0).abs()


    # ewm 메소드를 호출하여 지수이동평균을 구한다.
    au      = gain.ewm(alpha=1/14, min_periods=14).mean()
    ad      = loss.ewm(alpha=1/14, min_periods=14).mean()

    rs = au / ad
    rsi = 100 - (100 / (1 + rs))

    print(np.round(rsi, 2))



    closeClient(client)

    print('Main End')
