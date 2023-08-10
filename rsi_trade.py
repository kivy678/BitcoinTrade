# -*- coding:utf-8 -*-

#############################################################################

from binance.helpers import round_step_size


import warnings
warnings.filterwarnings("ignore")

import time
import ta

import pandas as pd
import numpy as np

from util.bapi import *
from util.Logger import LOG

import pprint

#############################################################################

np.set_printoptions(suppress=True)

BTC = 'BTC'
COIN = 'BTCUSDT'
VOLUME = 0.002

buy_order_id = None
sell_order_id = None

KLINE_INTERVAL = Client.KLINE_INTERVAL_15MINUTE

#############################################################################

class BuyWaitUntilContracted(Exception): pass
class SellWaitUntilContracted(Exception): pass
class BuyOrder(Exception): pass
class SellOrder(Exception): pass



def init_trade(client):

    #바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
    server_time_sync(client)

    # 최소 매매 자금 체크
    wallet_size = get_asset_balance(client)
    LOG.info(f'현재 가지고 있는 USDT: {wallet_size}')

    coin_amount = get_asset_balance(client, BTC)
    if (coin_amount == 0) and (wallet_size < get_require_minsize(client, COIN)):
        LOG.info(f'{COIN} 를 매매할 돈이 부족합니다.')
        exit()


def get_rsi():
    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol='BTCUSDT',
                                interval=KLINE_INTERVAL,
                                limit=250)

    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)

    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

    rsi = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()

    return int(rsi.loc[249])


def ready_trade(client):

    # API제한 체크
    bool_limit, query_limit = check_api_limit(client)
    if bool_limit:
        LOG.info('API 제한...')
        time.sleep(60)

    # 60초 sleep
    if get_asset_balance(client, 'BNB') == 0:
        LOG.info(f'60초 동안 쉽니다.')
        time.sleep(60)


    rsi = get_rsi()
    last_price = get_recent_price(client, COIN)
    coin_amount = get_asset_balance(client, BTC)
    LOG.info(f'({query_limit})#현재 RSI와 {COIN} 가격 및 보유수: {rsi}#{last_price}#{coin_amount}')

    return rsi, coin_amount


def buy_logic(client, buy_log_cnt):
    #############################################################################
    # 매수 로직
    #############################################################################
    while True:
        try:
            # 매수 체결이 이루어진 상태이고 프로그램 재시작으로 인해 buy_order_id를 알 수 없는 경우
            if get_asset_balance(client, BTC) > get_require_min_qty(client, COIN):
                return

            # 매수된 코인이 없기 때문에 매수 주문서 접수 대기. 간혹 잔여 코인이 있을 수도 있음
            elif buy_order_id is None:
                if get_rsi() < 30:
                    buy_price = int(get_recent_price(client, COIN)) + 1

                    try:
                        order_info  = create_buy(client, COIN, buy_price, qty_lot(client, VOLUME, COIN))
                        qty         = order_info.get('origQty')
                        complte_qty = order_info.get('cummulativeQuoteQty')
                        buy_order_id = order_info.get('orderId')
                        status      = order_info.get('status')
                        price       = order_info.get('price')

                        coin_amount += float(qty)

                        LOG.info(f'신규 매수 주문 접수 완료: {get_rsi()}${price}#{qty}')
                        
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
            time.sleep(60)


        if buy_log_cnt == 360:
            ready_trade(client)
            LOG.info('매수 주문 체결 30분간 대기')
            buy_log_cnt = 1
        else:
            buy_log_cnt += 1

        time.sleep(5)


def sell_logic(client, sell_log_cnt):
    #############################################################################
    # 매도 로직
    #############################################################################
    while True:
        try:
            # 매도 체결이 이루어진 상태이고 프로그램 재시작으로 인해 sell_order_id를 알 수 없는 경우
            if get_asset_balance(client, BTC) <= get_require_min_qty(client, COIN):
                return

            # 매도된 코인이 없기 때문에 매도 주문서 접수 대기. 간혹 잔여 코인이 있을 수도 있음
            elif sell_order_id is None:
                if get_rsi() > 70:
                    sell_price = int(get_recent_price(client, COIN)) + 1 
                    loseTrigger = sell_price - 500 
                    coin_amount = get_asset_balance(client, BTC)

                    try:
                        order_info  = create_sell(client, COIN, sell_price, qty_lot(client, coin_amount, COIN), loseTrigger)
                        for info in order_info.get('orderReports'):
                            if info.get('type') == 'STOP_LOSS_LIMIT' and info.get('status') == 'NEW':
                                stop_loss = info.get('stopPrice')

                            elif info.get('type') == 'LIMIT_MAKER' and info.get('status') == 'NEW':
                                price = info.get('price')
                                origQty = info.get('origQty')
                                sell_order_id = info.get('orderId')

                        LOG.info(f'신규 매도 주문 접수: {get_rsi()}${price}${origQty}')
                        
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
            time.sleep(60)


        if sell_log_cnt == 360:
            ready_trade(client)
            LOG.info('매도 주문 체결 30분간 대기')
            sell_log_cnt = 1
        else:
            sell_log_cnt += 1


        time.sleep(5)



if __name__ == '__main__':

    print('Main Start')

    client = getClient()
    assert client

    init_trade(client)
    rsi, coin_amount = ready_trade(client)


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
        buy_log_cnt = 1
        sell_log_cnt = 1
        

        buy_logic(client, buy_log_cnt)
        sell_logic(client, sell_log_cnt)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
