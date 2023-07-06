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
COIN = 'BTCUSDT'
VOLUME = 0.0006

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
        if check_api_limit(client):
            print('API 제한...')
            time.sleep(60)


        # 60초 sleep
        if get_asset_balance(client, 'BNB') == 0:
            LOG.info(f'60초 동안 쉽니다.')
            time.sleep(60)
        

        # 최소 매매 자금 체크
        wallet_size = get_asset_balance(client)
        LOG.info(f'현재 가지고 있는 USDT: {wallet_size}')


        if wallet_size < get_require_minsize(client, COIN):
            LOG.info(f'{COIN} 를 매매할 돈이 부족합니다.')
            exit()


        a = get_orders(client, COIN)
        for i in a:
            if i.get('status') in (ORDER_STATUS_NEW, ORDER_STATUS_FILLED):
                break

        #get_rsi()



        print('sleep')
        time.sleep(60)

    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
