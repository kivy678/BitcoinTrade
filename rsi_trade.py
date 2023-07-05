# -*- coding:utf-8 -*-

#############################################################################

import ta
import functools
from operator import itemgetter

import pandas as pd
import numpy as np
from pandas import Series, DataFrame

import time
from util.bapi import *
from util.Logger import LOG

#############################################################################

np.set_printoptions(suppress=True)
COIN = 'BTCUSDT'
VOLUME = 0.0006

#############################################################################


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


        print('sleep')
        time.sleep(60)

    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
