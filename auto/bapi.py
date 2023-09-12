# -*- coding:utf-8 -*-

#############################################################################

import subprocess as sp

from env import *

import os
import time
import win32api

from binance import Client
from binance.exceptions import BinanceAPIException

from binance.enums import *
from binance.helpers import round_step_size

from query import *
from Logger import LOG

from db import SQLite

#############################################################################

DB_CONFIG = {'database': r'var/database.db'}

#############################################################################

# https://developers.binance.com/docs/binance-trading-api/spot#api-key-restrictions
def check_api_limit(client):
    resp = client.response.headers.get('x-mbx-used-weight-1m')
    if int(resp) >= 1200:
        return True, int(resp)
    else:
        return False, int(resp)


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

#############################################################################


# 지갑에서 수량 가져오기
def get_asset_balance(client, symbol='USDT'):
    if symbol.startswith('USDT'):
        pass
    else:
        symbol = symbol.replace('USDT', '')
    
    return float(client.get_asset_balance(asset=symbol).get('free'))



# API 제한 가져오기
def get_exchange_info_api(client):
    
    for row in client.get_exchange_info().get('rateLimits'):
        yield row


# 모든 코인 거래 정보 가져오기
# 레버리지 코인 제외, USDT로 거래, 트레이딩 가능
def get_exchange_info_usdt(client):
    
    info =  client.get_exchange_info()
    exclude_coin1   = ['UP', 'DOWN', 'BEAR', 'BULL', 'BNBUSDT'] # 레버리지 코인
    exclude_coin2   = ['USDC', 'BUSD', 'TUSD', 'DAI', 'EUR'] # 스테이블 코인

    for x in info.get('symbols'):
        symbol_name = x.get('symbol')

        # USDT 교환이고 레버리지 코인이 아니며, 스테이블끼리 교환이아니며 트레이딩이 가능한 코인
        if symbol_name.endswith('USDT') and                                             \
            all(exclude not in symbol_name for exclude in exclude_coin1) and            \
            not any(symbol_name.startswith(exclude) for exclude in exclude_coin2) and   \
            x.get('status') == 'TRADING':

            yield x


#############################################################################


# 최소 가격의 간격
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_tick_size(info):
    for types in info.get('filters'):
        if  types.get('filterType') == 'PRICE_FILTER':
            return float(types.get('tickSize'))


# 최소 수량의 간격
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_step_size(info):
    for types in info.get('filters'):
        if  types.get('filterType') == 'LOT_SIZE':
            return float(types.get('stepSize'))


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



def get_size(symbol, size_name):
    conn = SQLite(DB_CONFIG)
    row = conn.query(query_get_size_symbol.format(size_name), (symbol,))
    conn.close()

    return row[0][0] if row != () else False


#############################################################################

# 오더북 가져오기
def get_open_orders(client):
    return client.get_open_orders()


# 주문 취소
def cancle_order(client, symbol, orderId):
    try:
        return client.cancel_order(symbol=symbol, orderId=orderId)
    
    except BinanceAPIException as e:
        return False

#############################################################################

# 마지막 거래 가격
def get_recent_price(client, symbol):
    tick_size = get_size(symbol, 'tick_size')
    for info in client.get_recent_trades(symbol=symbol, limit=1):
        return round_step_size(info.get('price'), tick_size)


# 마지막 평균 거래 가격
def get_avg_price(client, symbol):
    tick_size = get_size(symbol, 'tick_size')
    avg_price = client.get_avg_price(symbol=symbol).get('price')

    return round_step_size(avg_price, tick_size)


# 실제 코인 거래시 최소 코인 수량
# BTCUSDT를 거래할 경우 BTC를 가르킴
def get_require_min_qty(client, symbol, alpha_qty=10):
    recent_price    = get_recent_price(client, symbol)    # 현재 가격
    tick_size       = get_size(symbol, 'tick_size')       # 가격의 최소 요구 간격
    min_noti        = get_size(symbol, 'min_noti')        # 구매시 최소 요구 USDT
    step_size       = get_size(symbol, 'step_size')       # 수량의 최소 요구 간격


    qty     = min_noti / recent_price
    # 가격이 계속 변동하기 때문에 가격이 상승할 경우 구매 요구 수량이 늘어나므로 최소 요구간격의 배수 만큼 더해준다.
    alpha   = step_size * alpha_qty

    return round_step_size(qty+alpha, step_size)


def sell_asset_balance(client, symbol):
    step_size = get_size(symbol, 'step_size')
    return round_step_size(get_asset_balance(client, symbol), step_size)


#############################################################################

# 시간전 캔들 정보 가져오기
def get_historical_klines_hour(client, symbol, h=24):
    candles = client.get_historical_klines(symbol,
                                           Client.KLINE_INTERVAL_1MINUTE,
                                           f'{h} hour ago UTC')

    return candles

#############################################################################

# 주문서 상태
def get_order_status(client, symbol, orderId):
    return client.get_order(symbol=symbol, orderId=orderId).get('status')


# 매수 market 주문
def create_market_buy(client, symbol, quantity):
    return client.order_market_buy(symbol=symbol,
                                  quantity=quantity)



# 매도 market 주문
def create_market_sell(client, symbol, quantity):
    return client.order_market_sell(symbol=symbol,
                                 quantity=quantity)



# 매수 Limit 주문
def create_limit_buy(client, symbol, price, quantity):
    return client.order_limit_buy(symbol=symbol,
                                  price=float_to_str(price),
                                  quantity=quantity)



# limit 매도 주문
def create_limit_sell(client, symbol, price, quantity):
    return client.order_limit_sell(symbol=symbol,
                                 price=float_to_str(price),
                                 quantity=quantity)



def order_limit_buy(client, symbol, alpha_price=2):
    tick_size   = get_size(symbol, 'tick_size')
    buy_price   = get_recent_price(client, symbol) - (tick_size * alpha_price)
    qty         = get_require_min_qty(client, symbol, alpha_qty=10)
    
    try:
        order_info  = create_limit_buy(client, symbol, buy_price, qty)
        qty         = order_info.get('origQty')
        complte_qty = order_info.get('cummulativeQuoteQty')
        buy_order_id = order_info.get('orderId')
        status      = order_info.get('status')
        price       = order_info.get('price')
        
        LOG.info(f'신규 매수 주문 접수 완료: {symbol}##{price}##{qty}')

        return buy_order_id
        
    except BinanceAPIException as e:
        LOG.info(f'신규 매수 주문 접수 실패: {symbol}#{e}')

        return False


def order_limit_sell(client, symbol, alpha_price=2):
    tick_size   = get_size(symbol, 'tick_size')
    sell_price  = get_recent_price(client, symbol) + (tick_size * alpha_price)
    coin_amount = sell_asset_balance(client, symbol)

    try:
        order_info      = create_limit_sell(client, symbol, sell_price, coin_amount)
        qty             = order_info.get('origQty')
        sell_order_id   = order_info.get('orderId')
        status          = order_info.get('status')
        price           = order_info.get('price')

        LOG.info(f'신규 매도 주문 접수: {symbol}##{price}##{qty}')

        return sell_order_id
        
    except BinanceAPIException as e:
        LOG.info(f'신규 매도 주문 실패 : {symbol}#{e}')

        return False



def order_market_buy(client, symbol, alpha_qty=10):
    qty            = get_require_min_qty(client, symbol, alpha_qty)
    
    try:
        order_info  = create_market_buy(client, symbol, qty)
        qty         = order_info.get('origQty')
        complte_qty = order_info.get('cummulativeQuoteQty')
        buy_order_id = order_info.get('orderId')
        status      = order_info.get('status')
        price       = order_info.get('price')
        
        LOG.info(f'마켓 매수 주문 체결 완료: {symbol}##{price}##{qty}')

        return True
        
    except BinanceAPIException as e:
        LOG.info(f'마켓 매수 주문 접수 실패: {symbol}#{e}')

        return False


def order_market_sell(client, symbol):
    coin_amount = sell_asset_balance(client, symbol)

    try:
        order_info      = create_market_sell(client, symbol, coin_amount)
        qty             = order_info.get('origQty')
        sell_order_id   = order_info.get('orderId')
        status          = order_info.get('status')
        price           = order_info.get('price')

        LOG.info(f'마켓 매도 주문 체결 완료: {symbol}##{price}##{qty}')

        return True


    except BinanceAPIException as e:
        LOG.info(f'마켓 매도 주문 실패 : {symbol}#{e}')

        return False


#############################################################################

def get_my_trades(client, symbol, startTime):
    ret =  client.get_my_trades(symbol=symbol,
                                startTime=startTime
                                )

    return ret

#############################################################################

