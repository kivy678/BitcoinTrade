# -*- coding:utf-8 -*-

#############################################################################

import functools
from operator import itemgetter

import pandas as pd
from pandas import Series, DataFrame
import numpy as np

import time
from util.bapi import *
from util.Logger import LOG

#############################################################################

np.set_printoptions(suppress=True)
COIN = 'BTCUSDT'
VOLUME = 0.0006

#############################################################################

# Grouping Price
def convert_round(x, grouping=8):
    return [int(int(float(x[0])) / grouping) * grouping, float(x[1])]


def get_grouping_data(order_data):
    buy_orderbook_array = np.array(list(map(
                          functools.partial(convert_round, grouping=100), order_data)), dtype='float64')

    # 중복들을 제거해준다.
    orderbook_price = np.unique(buy_orderbook_array[:,0])
    grouping_price = [ (i, np.sum(buy_orderbook_array[buy_orderbook_array[:,0] == i,1])) for i in orderbook_price ]


    # 비트코인 물량 기준으로 내림차순 정렬
    return sorted(grouping_price, key=itemgetter(1), reverse=True)


if __name__ == '__main__':

    print('Main Start')
     
    client = getClient()
    assert client


    while True:
        #바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
        server_time_sync(client)


        # API제한 체크
        if check_api_limit(client):
            print('API 제한...')
            time.sleep(60)


        # 최소 매매 자금 체크
        wallet_size = get_asset_balance(client)
        LOG.info(f'현재 가지고 있는 USDT: {wallet_size}')


        if wallet_size < get_require_minsize(client, COIN):
            LOG.info(f'{COIN} 를 매매할 돈이 부족합니다.')
            exit()


        # 호가창 정보 중 매수를 최대로 가져온다.
        buy_order       = client.get_order_book(symbol='BTCUSDT', limit=5000)['bids']
        buy_order_data  = get_grouping_data(buy_order)
        buy_price       = buy_order_data[0][0]            # 가장 물량이 많이 모여 있는 가격이다.


        # 코인을 매수한다.
        order_info  = create_buy(client, COIN, buy_price, VOLUME)
        qty         = order_info.get('origQty')
        complte_qty = order_info.get('cummulativeQuoteQty')
        orderId     = order_info.get('orderId')
        status      = order_info.get('status')
        price       = order_info.get('price')

     
        if status == ORDER_STATUS_NEW:
            LOG.info(f'신규 주문 접수: {orderId}:{qty}:{status}')


        # 매수 체결 기다리기
        try:
            cnt = 0
            while True:

                if get_order_status(client, COIN, orderId) in (ORDER_STATUS_FILLED, ORDER_STATUS_CANCELED):
                    break

                elif cnt == 5:       # 1분씩 5번 주문상태를 확인하여 체결이 되지 않았으면, 취소
                    cancle_order(client, COIN, orderId)
                    raise BuyOrderExpireError(f'[*] Cancel Order: {orderId}')

                else:
                    cnt += 1
                    time.sleep(60)

            LOG.info(f'매수 체결 완료: {orderId}:{price}:{qty}')

        except BuyOrderExpireError:     # 다시 되돌아간다.
            continue

        except BinanceAPIException as e:
            print('BinanceAPI Error: ', e)
            break


        # 매도 체결 기다리기
        try:
            sell_price  = price + 300
            loseTrigger = price - 300

            order_info = create_oco_sell(client,
                                        SYMBOL,
                                        sell_price,
                                        QUANTITY,
                                        loseTrigger,
                                        loseTrigger)

            qty         = order_info.get('origQty')
            complte_qty = order_info.get('cummulativeQuoteQty')
            orderId     = order_info.get('orderId')
            status      = order_info.get('status')
            price       = order_info.get('price')

            LOG.info(f'매도 체결 완료: {orderId}:{price}:{qty}')


        except BinanceAPIException as e:
            print('BinanceAPI Error: ', e)
            break


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
