# -*- coding:utf-8 -*-

#############################################################################

import functools
from operator import itemgetter

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


# Grouping Price
def convert_round(x, grouping=8):
    return [int(int(float(x[0])) / grouping) * grouping, float(x[1])]


if __name__ == '__main__':
    client = getClient()
    assert client

    server_time_sync(client)


    # 현재 호가창 정보를 가져옵니다.
    # 'asks'    # Sell
    # 'bids'    # Buy
    order = client.get_order_book(symbol='POLYXUSDT', limit=3)
    #pprint.pprint(order)


    buy_order = client.get_order_book(symbol='BTCUSDT', limit=100)['bids']
    for buy in buy_order:
        # [가격, 수량]  <- 문자열이기 때문에 소숫점을 없애기 위해 먼저 실수로 변환하고 정수로 변환한다.
        price = int(float(buy[0]))
        qty = float(buy[1])

        # 그룹핑할 수치로 나눠준다. 28436을 10으로 나누게 되면 몫이 2843 나머지가 6이 된다.
        # 그리고 다시 10을 곱해준다.
        price = int(price / 10)       
        price = price * 10
    

    # 소숫점 자리가 길면 e 로 표시된다. 자릿수를 잘라서 표시
    np.set_printoptions(formatter={'float_kind': lambda x: "{0:0.3f}".format(x)})

    buy_order = client.get_order_book(symbol='BTCUSDT', limit=5000)['bids']
    buy_orderbook_array = np.array(list(map(
                          functools.partial(convert_round, grouping=100), buy_order)), dtype='float64')
    print(buy_orderbook_array)



    resp = client.response.headers.get('x-mbx-used-weight-1m')
    assert int(resp) <= 1200
    
    closeClient(client)

    print('Main End')
