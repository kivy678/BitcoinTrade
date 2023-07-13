# -*- coding:utf-8 -*-

#############################################################################

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
VOLUME = 0.003
#VOLUME = 0.0006
buy_orderId = None
sell_orderId = None

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
    LOG.info(f'({query_limit}) 현재 RSI와 {COIN} 가격 및 보유수: {rsi}, {last_price}, {coin_amount}')

    return rsi, coin_amount



def get_rsi():
    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol='BTCUSDT',
                                interval=KLINE_INTERVAL,
                                limit=14)

    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)

    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

    rsi = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()

    return int(rsi.loc[13])



if __name__ == '__main__':

    print('Main Start')

    client = getClient()
    assert client

    init_trade(client)
    rsi, coin_amount = ready_trade(client)

    # 프로그램 재시작으로 인한 매수 주문이 접수 되었으나 오더 아이디 값이 초기화 되었을 경우 오더북에서 가져와야한다.
    if buy_orderId is None:
        for info in get_orders(client, COIN):
            if info.get('side') == 'BUY' and                                     \
                info.get('status') == ORDER_STATUS_NEW:
                buy_orderId = info.get('orderId')


    # 프로그램 재시작으로 인한 매도 주문이 접수 되었으나 오더 아이디 값이 초기화 되었을 경우 오더북에서 가져와야한다.
    if sell_orderId is None:
        for info in get_orders(client, COIN):
            if info.get('side') == 'SELL' and                                    \
                info.get('type') == ORDER_TYPE_LIMIT_MAKER and                   \
                info.get('status') == ORDER_STATUS_NEW:
                sell_orderId = info.get('orderId')


    time.sleep(1)


    #############################################################################

    while True:

        if coin_amount == 0:
            # 매수 로직
            while True:
                rsi, coin_amount = ready_trade(client)

                try:
                    # 오더 아이디가 존재할 때 상태 값에 따라 분기
                    if buy_orderId is not None:
                        order_status = get_order_status(client, COIN, buy_orderId)

                        # 매수 주문이 체결될 때까지 대기
                        if order_status == ORDER_STATUS_NEW:
                            raise(BuyWaitUntilContracted)


                        # 이전에 접수 되었던 예약 매수 주문이 취소되었거나 유효기간이 지나면 다시 예약 매수 주문이 접수될 때까지 대기
                        elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                            LOG.info('매수 주문 접수가 취소. 신규 매수 주문 접수를 대기')
                            buy_orderId = None
                            raise(BuyOrder)


                        # 주문이 체결된 상태이며, 매도 로직으로 넘어간다.
                        elif order_status == ORDER_STATUS_FILLED:
                            LOG.info(f'매수 주문 체결이 완료. 주문번호: {buy_orderId}')
                            buy_orderId = None
                            break

                    # 오더북에도 없을 경우 예약 매수 주문이 접수될 때까지 대기
                    else:
                        raise(BuyOrder)


                except BuyOrder:
                    #매수 로직
                    if (rsi < 30) and (buy_orderId is None):
                        # 1 비싸게 산다
                        buy_price = int(get_recent_price(client, COIN)) + 1

                        # 코인을 매수한다.
                        try:
                            order_info  = create_buy(client, COIN, buy_price, VOLUME)
                            qty         = order_info.get('origQty')
                            complte_qty = order_info.get('cummulativeQuoteQty')
                            buy_orderId = order_info.get('orderId')
                            status      = order_info.get('status')
                            price       = order_info.get('price')

                            LOG.info(f'신규 매수 주문 접수 완료: {buy_orderId}, {price}, {qty}')

                        except binance.exceptions.BinanceAPIException:
                            LOG.info('신규 매수 주문 접수 실패')


                # 매수 주문이 체결될 때까지 대기
                except BuyWaitUntilContracted:
                    pass


                print('매수 주문 체결 10초간 대기')
                time.sleep(10)
                continue

        else:
            # 매도 로직
            while True:
                rsi, coin_amount = ready_trade(client)

                try:
                    # 오더 아이디가 존재할 때 상태 값에 따라 분기
                    if sell_orderId is not None:
                        order_status = get_order_status(client, COIN, sell_orderId)

                        # 매도 주문이 체결될 때까지 대기
                        if order_status == ORDER_STATUS_NEW:
                            raise(SellWaitUntilContracted)


                        # 이전에 접수 되었던 예약 매도 주문이 취소되었거나 유효기간이 지나면 다시 예약 매도 주문이 접수될 때까지 대기
                        elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                            LOG.info('매도 주문 접수가 취소. 신규 매도 주문 접수를 대기')
                            sell_orderId = None
                            raise(SellOrder)


                        # 주문이 체결된 상태이며, 다시 매수 로직으로 넘어간다.
                        elif order_status == ORDER_STATUS_FILLED:
                            LOG.info(f'매도 주문 체결이 완료. 주문번호: {buy_orderId}')
                            sell_orderId = None
                            break


                    # 오더북에도 없을 경우 예약 매도 주문이 접수될 때까지 대기
                    else:
                        raise(SellOrder)


                except SellOrder:
                    if (rsi > 70) and (coin_amount >= VOLUME):
                        # 1 비싸게 판다.
                        sell_price = int(get_recent_price(client, COIN)) + 1 
                        loseTrigger = sell_price - 1000

                        # 코인을 매도한다.
                        try:
                            order_info  = create_sell(client, COIN, sell_price, coin_amount, loseTrigger)
                            for info in order_info.get('orderReports'):
                                if info.get('type') == 'STOP_LOSS_LIMIT' and info.get('status') == 'NEW':
                                    stop_loss = info.get('stopPrice')

                                elif info.get('type') == 'LIMIT_MAKER' and info.get('status') == 'NEW':
                                    price = info.get('price')
                                    origQty = info.get('origQty')
                                    sell_orderId = info.get('orderId')

                            LOG.info(f'신규 매도 주문 접수: {sell_orderId}, {price}, {origQty}, {stop_loss}')


                        except binance.exceptions.BinanceAPIException:
                            LOG.info('신규 매도 주문 실패')


                # 매도 주문이 체결될 때까지 대기
                except SellWaitUntilContracted:
                    pass


                print('매도 주문 체결 10초간 대기')
                time.sleep(10)
                continue



    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
