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
VOLUME = 0.0006
orderId = None

#############################################################################


def get_rsi():
    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol='BTCUSDT',
                                interval=Client.KLINE_INTERVAL_15MINUTE,
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


    while True:
        #바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
        server_time_sync(client)


        # API제한 체크
        bool_limit, query_limit = check_api_limit(client)
        if bool_limit:
            LOG.info('API 제한...')
            time.sleep(60)

        # 60초 sleep
        if get_asset_balance(client, 'BNB') == 0:
            LOG.info(f'60초 동안 쉽니다.')
            time.sleep(60)
            continue


        # 최소 매매 자금 체크
        wallet_size = get_asset_balance(client)
        LOG.info(f'현재 가지고 있는 USDT: {wallet_size}')


        if wallet_size < get_require_minsize(client, COIN):
            LOG.info(f'{COIN} 를 매매할 돈이 부족합니다.')
            exit()


        is_buy = False
        coin_amount = get_asset_balance(client, BTC)

        if coin_amount >= VOLUME:
            is_buy = True

        else:
            for buy_order_status in get_orders(client, COIN):
                if (buy_order_status.get('status') in (ORDER_STATUS_NEW, ORDER_STATUS_FILLED)):
                    is_buy = True
                    break


        rsi = get_rsi()
        last_price = get_recent_price(client, COIN)
        LOG.info(f'({query_limit}) 현재 RSI와 {COIN} 가격 및 보유수: {rsi}, {last_price}, {coin_amount}')


        if (rsi < 30) and (is_buy is False):
            buy_price = int(get_recent_price(client, COIN))

            # 코인을 매수한다.
            order_info  = create_buy(client, COIN, buy_price+5, VOLUME)
            qty         = order_info.get('origQty')
            complte_qty = order_info.get('cummulativeQuoteQty')
            orderId     = order_info.get('orderId')
            status      = order_info.get('status')
            price       = order_info.get('price')

            LOG.info(f'신규 주문 접수: {orderId}:{price}:{qty}:{status}')


        elif (rsi > 70) and (coin_amount >= VOLUME):
            sell_price = int(get_recent_price(client, COIN))
            loseTrigger = sell_price - 1000

            # 코인을 매도한다.
            order_info  = create_sell(client, COIN, sell_price-5, coin_amount, loseTrigger)

            qty         = order_info.get('origQty')
            complte_qty = order_info.get('cummulativeQuoteQty')
            orderId     = order_info.get('orderId')
            status      = order_info.get('status')
            price       = order_info.get('price')

            LOG.info(f'매도 체결 완료: {orderId}:{price}:{qty}:{status}')


        print('sleep')
        time.sleep(5)

    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
