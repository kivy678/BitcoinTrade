# -*- coding:utf-8 -*-

#############################################################################

import pprint
import time
import win32api

from binance import Client
from binance.exceptions import BinanceAPIException

from binance.enums import *
from binance.helpers import round_step_size

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


def float_to_str(f):
    return format(f, '.8f')


def check_api_limit(client):
    resp = client.response.headers.get('x-mbx-used-weight-1m')
    if int(resp) > 1200:
        return True
    else:
        return False



# 최소 거래 사이즈 확인 (금액)
def get_require_minsize(client, symbol):
    info = client.get_symbol_info(symbol)

    for types in info.get('filters'):
        if types.get('filterType') == 'NOTIONAL':
            return float(types.get('minNotional'))



# 지갑에서 수량 가져오기
def get_asset_balance(client, asset='USDT'):
    return float(client.get_asset_balance(asset=asset).get('free'))


# 매수 Limit 주문
def create_buy(client, symbol, price, quantity):
    return client.order_limit_buy(symbol=symbol,
                                  price=float_to_str(price),
                                  quantity=quantity)

# 주문서 상태
def get_order_status(client, symbol, orderId):
    return client.get_order(symbol=symbol, orderId=orderId).get('status')



# 주문 취소
def cancle_order(client, symbol, orderId):
    return client.cancel_order(symbol=symbol, orderId=orderId)


# 
def get_orders(client, symbol):
    return client.get_open_orders(symbol=symbol)

