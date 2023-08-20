# -*- coding:utf-8 -*-

#############################################################################

from env import *

import os
import time
import win32api

from binance import Client
from binance.exceptions import BinanceAPIException

from binance.enums import *
from binance.helpers import round_step_size

from util.Logger import LOG

#############################################################################

CONTROL_SIZE_QTY    = 10
CONTROL_SIZE_PRICE  = 2

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


# 모든 코인 거래 정보 가져오기
# 레버리지 코인 제외, USDT로 거래, 트레이딩 가능
def get_exchange_info_usdt(client):
    
    info =  client.get_exchange_info()
    exclude_coin   = ['UP', 'DOWN', 'BEAR', 'BULL', 'BNBUSDT']     # 레버리지 코인은 제외

    for x in info.get('symbols'):
        symbol_name = x.get('symbol')

        # USDT 이고 레버리지 코인이 아니며, 트레이딩이 가능한 코인
        if symbol_name.endswith('USDT') and                                     \
            all(exclude not in symbol_name for exclude in exclude_coin) and     \
            x.get('status') == 'TRADING':

            yield x


# 오더북 가져오기
def get_open_orders(client):
    return client.get_open_orders()


# 최소 가격의 간격
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_tick_size(info):
    for types in info.get('filters'):
        if  types.get('filterType') == 'PRICE_FILTER':
            return float(types.get('tickSize'))


def get_tick_size_from_order_book(a_symbol, order_book):
    for symbol in order_book:
        if symbol == a_symbol:
            return order_book[symbol].get('tick_size')


# 최소 수량의 간격
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_step_size(info):
    for types in info.get('filters'):
        if  types.get('filterType') == 'LOT_SIZE':
            return float(types.get('stepSize'))


def get_step_size_from_order_book(a_symbol, order_book):
    for symbol in order_book:
        if symbol == a_symbol:
            return order_book[symbol].get('step_size')


# 최소 수량
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_lot(info):
    for types in info.get('filters'):
        if  types.get('filterType') == 'LOT_SIZE':
            return float(types.get('minQty'))


# 최소 가격
# BTCUSDT를 거래할 경우 USDT를 가르킴
def get_require_min_notional(info):
    for types in info.get('filters'):
        if types.get('filterType') == 'NOTIONAL':
            return float(types.get('minNotional'))


def get_min_notional_from_order_book(a_symbol, order_book):
    for symbol in order_book:
        if symbol == a_symbol:
            return order_book[symbol].get('min_noti')


# 1시간전 캔들 정보 가져오기
def get_historical_klines_1hour(client, symbol):
    candles = client.get_historical_klines(symbol,
                                           Client.KLINE_INTERVAL_1MINUTE,
                                           '1 hour ago UTC')

    return candles


# 마지막 거래 가격
def get_recent_price(client, symbol, order_book):
    tick_size = get_tick_size_from_order_book(symbol, order_book)
    for info in client.get_recent_trades(symbol=symbol, limit=1):
        return round_step_size(info.get('price'), tick_size)


# 마지막 평균 거래 가격
def get_avg_price(client, symbol, order_book):
    avg_price = client.get_avg_price(symbol=symbol).get('price')
    tick_size = get_tick_size_from_order_book(symbol, order_book)
    return round_step_size(avg_price, tick_size)


# 실제 코인 거래시 최소 코인 수량
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_qty(client, symbol, order_book):
    qty = get_min_notional_from_order_book(symbol, order_book) / get_recent_price(client, symbol, order_book)
    qty = qty + get_step_size_from_order_book(symbol, order_book) * CONTROL_SIZE_QTY
    return round_step_size(qty, get_step_size_from_order_book(symbol, order_book))


# 지갑에서 수량 가져오기
def get_asset_balance(client, symbol='USDT'):
    if symbol.startswith('USDT'):
        pass
    else:
        symbol = symbol.replace('USDT', '')
    
    return float(client.get_asset_balance(asset=symbol).get('free'))


def sell_asset_balance(client, symbol, order_book):
    step_size = get_step_size_from_order_book(symbol, order_book)
    return round_step_size(get_asset_balance(client, symbol), step_size)


# 주문서 상태
def get_order_status(client, symbol, orderId):
    return client.get_order(symbol=symbol, orderId=orderId).get('status')


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


# 주문 취소
def cancle_order(client, symbol, orderId):
    return client.cancel_order(symbol=symbol, orderId=orderId)


def order_buy(client, symbol, order_book):
    tick_size = get_tick_size_from_order_book(symbol, order_book)
    buy_price = get_recent_price(client, symbol, order_book) + (tick_size * CONTROL_SIZE_PRICE)
    qty = get_require_min_qty(client, symbol, order_book)
    
    try:
        order_info  = create_buy(client, symbol, buy_price, qty)
        qty         = order_info.get('origQty')
        complte_qty = order_info.get('cummulativeQuoteQty')
        buy_order_id = order_info.get('orderId')
        status      = order_info.get('status')
        price       = order_info.get('price')

        order_book[symbol]['buy_orderId'] = buy_order_id
        LOG.info(f'신규 매수 주문 접수 완료: {symbol}##{price}##{qty}')

        return buy_order_id
        
    except BinanceAPIException as e:
        LOG.info(f'신규 매수 주문 접수 실패: {symbol}#{e}')



def order_sell(client, symbol, order_book):
    tick_size = get_tick_size_from_order_book(symbol, order_book)
    sell_price = get_recent_price(client, symbol, order_book) - (tick_size * CONTROL_SIZE_PRICE)
    coin_amount = sell_asset_balance(client, symbol, order_book)

    try:
        order_info      = create_sell(client, symbol, sell_price, coin_amount)
        qty             = order_info.get('origQty')
        sell_order_id   = order_info.get('orderId')
        status          = order_info.get('status')
        price           = order_info.get('price')

        order_book[symbol]['sell_orderId'] = sell_order_id

        LOG.info(f'신규 매도 주문 접수: {symbol}##{price}##{qty}')

        return sell_order_id
        
    except BinanceAPIException as e:
        LOG.info(f'신규 매도 주문 실패 : {symbol}#{e}')

