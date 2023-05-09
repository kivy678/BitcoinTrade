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


    # 코인의 정보를 가져옵니다.
    data = client.get_symbol_info('BTCUSDT')


    # 코인을 살 때 최소 매수량 정보를 가져옵니다.
    for types in data.get('filters'):
        if types.get('filterType') == 'LOT_SIZE':
            minQty = float(types.get('minQty'))
            break


    # 코인을 살 때 최소 매수가 정보를 가져옵니다.
    for types in data.get('filters'):
        if types.get('filterType') == 'MIN_NOTIONAL':
            minNotional = float(types.get('minNotional'))
            break


    #print('최소 매수량: ', minQty)
    #print('최소 매수가: ', minNotional)


    # 마켓가로 ETHUSDT를 매수합니다
    #ret = client.order_market(symbol='ETHUSDT', side='BUY', quantity=str(0.007))
    #print(ret)


    # 예약된 주문을 확인합니다.
    #res = client.get_open_orders(symbol='BTCUSDT')
    #for row in res:
    #    pprint.pprint(row)


    # 예약된 주문을 확인합니다.
    #res = client.get_order(symbol='BTCUSDT', orderId=13137452598)
    #pprint.pprint(res)


    # 예약된 주문을 취소합니다.
    client.cancel_order(symbol='BTCUSDT', orderId=13137452598)
    


    closeClient(client)

    print('Main End')
