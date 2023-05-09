# -*- coding:utf-8 -*-

#############################################################################

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


    # USDT 코인 보유량을 가져옵니다.
    data = client.get_asset_balance(asset='USDT')
    #print(data)


    # POLYBUSD 마지막 거래 정보를 5개 가져옵니다. 
    data = client.get_recent_trades(symbol='POLYBUSD', limit=5)
    #for row in data:
    #    print(row)


    # 2017-08-01 ~ 2022-08-24 동안 BTCUSDT 현물을 한 달 간격으로 거래가를 가져옵니다
    candles = client.get_historical_klines_generator('BTCUSDT',
                                                    Client.KLINE_INTERVAL_1MONTH,
                                                    '1 Aug, 2017',
                                                    '24 Aug, 2022')

    for row in candles:
        print(row)


    closeClient(client)

    print('Main End')
