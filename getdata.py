# -*- coding:utf-8 -*-

#############################################################################

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


    # USDT 코인 보유량을 가져옵니다.
    data = client.get_asset_balance(asset='USDT')
    print(data)


    closeClient(client)

    print('Main End')

