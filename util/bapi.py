# -*- coding:utf-8 -*-

#############################################################################

import win32api
import os

import pprint
import time

from binance import Client
from binance.exceptions import BinanceAPIException

from binance.enums import *
from binance.helpers import round_step_size

from env import *

#############################################################################

CONTROL_SIZE_QTY    = 10

#############################################################################


def getClient():
    try:
        return Client(BINANCE_ACCESS, BINANCE_SECRET, {"verify": False, "timeout": 20})
    except BinanceAPIException as e:
        print(e)
        return False


def closeClient(client):
    try:
        client.close_connection()
    except BinanceAPIException as e:
        print(e)
        return False


def SetSystemTime(year, mon, day, h, m, s):
    try:
        win32api.SetSystemTime(year,mon,0,day,h,m,s,0)

    except Exception as e:
        print('권한 실패')


def server_time_sync(client):
    try:
        server_time = client.get_server_time()
        gmtime = time.gmtime(int((server_time["serverTime"])/1000))

        SetSystemTime(gmtime[0],
                      gmtime[1],
                      gmtime[2],
                      gmtime[3],
                      gmtime[4],
                      gmtime[5])

    except BinanceAPIException as e:
        print(e)
        return False

def float_to_str(f):
    return format(f, '.8f')


def check_api_limit(client):
    resp = client.response.headers.get('x-mbx-used-weight-1m')
    if int(resp) >= 1200:
        return True, int(resp)
    else:
        return False, int(resp)


# 최소 가격의 간격
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_tick_size(client, symbol):
    for types in client.get_symbol_info(symbol).get('filters'):
        if  types.get('filterType') == 'PRICE_FILTER':
            return float(types.get('tickSize'))


# 최소 가격
# BTCUSDT를 거래할 경우 USDT를 가르킴
def get_require_min_notional(client, symbol):
    for types in client.get_symbol_info(symbol).get('filters'):
        if types.get('filterType') == 'NOTIONAL':
            return float(types.get('minNotional'))


# 최소 수량
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_lot(client, symbol):
    for types in client.get_symbol_info(symbol).get('filters'):
        if  types.get('filterType') == 'LOT_SIZE':
            return types.get('minQty')


# 최소 수량의 간격
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_lot_size(client, symbol):
    for types in client.get_symbol_info(symbol).get('filters'):
        if  types.get('filterType') == 'LOT_SIZE':
            return float(types.get('stepSize'))


# 마지막 거래 가격
def get_recent_price(client, symbol, tick_size):
    for info in client.get_recent_trades(symbol=symbol, limit=1):
        return round_step_size(info.get('price'), tick_size)


# 마지막 평균 거래 가격
def get_avg_price(client, symbol):
    avg_price = client.get_avg_price(symbol=symbol).get('price')
    tick_size = get_require_tick_size(client, symbol)

    return round_step_size(avg_price, tick_size)


# 실제 코인 거래시 최소 코인 수량
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_qty(client, symbol, min_noti, step_size, tick_size):
    qty = min_noti / get_recent_price(client, symbol, tick_size)
    qty = qty + step_size * CONTROL_SIZE_QTY
    return round_step_size(qty, step_size)


def qty_lot(qty, step_size):
    return round_step_size(qty, step_size)


# 지갑에서 수량 가져오기
def get_asset_balance(client, asset='USDT'):
    return float(client.get_asset_balance(asset=asset).get('free'))


# 매수 Limit 주문
def create_buy(client, symbol, price, quantity):
    return client.order_limit_buy(symbol=symbol,
                                  price=float_to_str(price),
                                  quantity=quantity)

# limit 매도 주문
def create_sell(client, symbol, price, quantity):
    return client.order_limit_sell(symbol=symbol,
                                 price=float_to_str(price),
                                 quantity=quantity)


# 주문서 상태
def get_order_status(client, symbol, orderId):
    return client.get_order(symbol=symbol, orderId=orderId).get('status')



# 주문 취소
def cancle_order(client, symbol, orderId):
    return client.cancel_order(symbol=symbol, orderId=orderId)


# 오더북 가져오기
def get_orders(client, symbol):
    return client.get_open_orders(symbol=symbol)


# limit 매도 주문
def create_oco_sell(client, symbol, price, quantity, loseTrigger):
    order_info = client.order_oco_sell(symbol=symbol,
                                       price=float_to_str(price),
                                       quantity=quantity,
                                       stopPrice=float_to_str(loseTrigger),
                                       stopLimitPrice=float_to_str(loseTrigger),
                                       stopLimitTimeInForce='GTC')

    return order_info



# 모든 심볼 정보 가져오기
def get_all_tickers(client, coin):
    return (row.get('symbol') for row in client.get_all_tickers() if row.get('symbol').endswith(coin))

