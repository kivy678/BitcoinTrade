# -*- coding:utf-8 -*-

#############################################################################

import time
import win32api

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


def check_api_limit(client):
    resp = client.response.headers.get('x-mbx-used-weight-1m')
    if int(resp) > 1200:
        return True
    else:
        return False



# 최소 거래 사이즈 확인
def get_require_minsize(client, symbol):
    info = client.get_symbol_info(symbol)
    for types in info.get('filters'):
        if types.get('filterType') == 'MIN_NOTIONAL':
            return float(types.get('minNotional'))



# 지갑에서 수량 가져오기
def get_asset_balance(client, asset='USDT'):
    return float(client.get_asset_balance(asset=asset).get('free'))

