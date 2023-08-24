# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import time
import ta

import pandas as pd
import numpy as np
np.set_printoptions(suppress=True)

from util.bapi import *
from util.Logger import LOG

import pprint

#############################################################################

BTC             = 'BTC'
COIN            = 'BTCUSDT'
VOLUME          = 0.002
CONTROL_SIZE_PRICE = 2

buy_order_id    = None
sell_order_id   = None

tick_size       = 0
step_size       = 0
min_lot         = 0
min_notional    = 0

KLINE_INTERVAL = Client.KLINE_INTERVAL_15MINUTE

#############################################################################


def init_trade(client, symbol):

    global tick_size
    global step_size
    global min_lot
    global min_notional


    #바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
    server_time_sync(client)

    # 최소 매매 자금 체크
    LOG.info(f'현재 가지고 있는 USDT: {get_asset_balance(client)}')
    tick_size       = get_require_tick_size(client, symbol)
    step_size       = get_require_min_lot_size(client, symbol)
    min_lot         = get_require_min_lot(client, symbol)
    min_notional    = get_require_min_notional(client, symbol)


def get_rsi(symbol):
    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol=symbol,
                                interval=KLINE_INTERVAL,
                                limit=250)

    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)

    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

    rsi = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()

    return np.round(rsi.loc[249], 2)


def ready_trade(client, symbol, log=''):

    global tick_size
    global step_size
    global min_lot
    global min_notional


    rsi         = get_rsi(symbol)
    last_price  = get_recent_price(client, symbol, tick_size)
    coin_amount = get_asset_balance(client, BTC)
    LOG.info(f'현재 RSI와 {symbol} 가격 및 보유수: {log}#{rsi}#{last_price}#{coin_amount}')

    return rsi, coin_amount


def buy_logic(client, symbol):
    #############################################################################
    # 매수 로직
    #############################################################################
    print('매수 로직')
    buy_log_cnt = 1

    global buy_order_id
    global sell_order_id
    global tick_size
    global step_size
    global min_lot
    global min_notional


    # 코인이 매수되었고 프로그램 재시작으로 인해 buy_order_id를 알 수 없는 경우
    if (sell_order_id is not None) or (get_asset_balance(client, BTC) > get_require_min_qty(client, symbol, min_notional, step_size, tick_size)):
        return


    while True:
        try:
            # 매수된 코인이 없기 때문에 매수 주문서 접수 대기. 간혹 잔여 코인이 있을 수도 있음
            if buy_order_id is None:
                rsi = get_rsi(symbol)
                if rsi < 30:
                    buy_price = get_recent_price(client, symbol, tick_size) + (tick_size * CONTROL_SIZE_PRICE)

                    try:
                        order_info  = create_buy(client, COIN, buy_price, qty_lot(VOLUME, step_size))
                        qty         = order_info.get('origQty')
                        complte_qty = order_info.get('cummulativeQuoteQty')
                        buy_order_id = order_info.get('orderId')
                        status      = order_info.get('status')
                        price       = order_info.get('price')

                        LOG.info(f'신규 매수 주문 접수 완료: {rsi}${price}#{qty}')
                        
                    except BinanceAPIException as e:
                        LOG.info(f'신규 매수 주문 접수 실패: {e}')
                        

            # 신규 매수 주문 접수가 완료 되었고 매수 체결이 이루어 졌는지 확인 해야한다.
            elif buy_order_id is not None:
                order_status = get_order_status(client, COIN, buy_order_id)
                
                # 매수 주문이 체결될 때까지 대기
                if order_status == ORDER_STATUS_NEW:
                    time.sleep(1)

                # 이전에 접수 되었던 예약 매수 주문이 취소되었거나 유효기간이 지나면 다시 예약 매수 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    LOG.info('매수 주문 접수가 취소. 신규 매수 주문 접수를 대기')
                    buy_order_id = None
                    

                # 주문이 체결된 상태이며, 매도 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    LOG.info(f'매수 주문 체결 완료')
                    buy_order_id = None
                    return

        except Exception as e:
            LOG.info(f'매수 로직 실패:{e}')
            time.sleep(60)


        if buy_log_cnt == 3:
            ready_trade(client, symbol, '매수 대기')
            buy_log_cnt = 1
        else:
            buy_log_cnt += 1

        time.sleep(60*5)



def sell_logic(client, symbol):
    #############################################################################
    # 매도 로직
    #############################################################################
    print('매도 로직')
    sell_log_cnt = 1

    global buy_order_id
    global sell_order_id
    global tick_size
    global step_size
    global min_lot
    global min_notional


    while True:
        try:
            # 매도된 코인이 없기 때문에 매도 주문서 접수 대기. 간혹 잔여 코인이 있을 수도 있음
            if sell_order_id is None:
                rsi = get_rsi(symbol)
                if rsi >= 70:
                    sell_price = get_recent_price(client, symbol, tick_size) - (tick_size * CONTROL_SIZE_PRICE)
                    coin_amount = get_asset_balance(client, BTC)

                    try:
                        order_info  = create_sell(client, COIN, sell_price, qty_lot(coin_amount, step_size))
                        origQty         = order_info.get('origQty')
                        sell_order_id   = order_info.get('orderId')
                        status          = order_info.get('status')
                        price           = order_info.get('price')

                        LOG.info(f'신규 매도 주문 접수: {rsi}${price}${origQty}')
                        
                    except BinanceAPIException as e:
                        LOG.info(f'신규 매도 주문 실패 : {e}')
                        

            # 신규 매도 주문 접수가 완료 되었고 매도 체결이 이루어 졌는지 확인 해야한다.
            elif sell_order_id is not None:
                order_status = get_order_status(client, COIN, sell_order_id)
                
                # 매도 주문이 체결될 때까지 대기
                if order_status == ORDER_STATUS_NEW:
                    time.sleep(1)
                    

                # 이전에 접수 되었던 예약 매도 주문이 취소되었거나 유효기간이 지나면 다시 예약 매도 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    LOG.info('매도 주문 접수가 취소. 신규 매도 주문 접수를 대기')
                    sell_order_id = None
                    

                # 매도 주문이 체결된 상태이며, 다시 매수 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    LOG.info(f'매도 주문 체결이 완료')
                    sell_order_id = None
                    return

        except Exception as e:
            LOG.info(f'매도 로직 실패:{e}')
            time.sleep(60)


        if sell_log_cnt == 3:
            ready_trade(client, symbol, '매도 대기')
            sell_log_cnt = 1
        else:
            sell_log_cnt += 1


        time.sleep(60*5)



if __name__ == '__main__':

    print('Main Start')

    client = getClient()
    assert client

    init_trade(client, COIN)
    rsi, coin_amount = ready_trade(client, COIN)


    # 프로그램 재시작으로 인한 매수 주문이 접수 되었으나 오더 아이디 값이 초기화 되었을 경우 오더북에서 가져와야한다.
    if buy_order_id is None:
        for info in get_orders(client, COIN):
            if info.get('side') == 'BUY' and                                     \
                info.get('status') == ORDER_STATUS_NEW:                          \
                buy_order_id = info.get('orderId')


    # 프로그램 재시작으로 인한 매도 주문이 접수 되었으나 오더 아이디 값이 초기화 되었을 경우 오더북에서 가져와야한다.
    if sell_order_id is None:
        for info in get_orders(client, COIN):
            if info.get('side') == 'SELL' and                                    \
                info.get('type') == ORDER_TYPE_LIMIT_MAKER and                   \
                info.get('status') == ORDER_STATUS_NEW:
                sell_order_id = info.get('orderId')


    time.sleep(1)
    

    while True:

        buy_logic(client, COIN)
        sell_logic(client, COIN)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
