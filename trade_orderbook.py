# -*- coding:utf-8 -*-

#############################################################################

import time
from util.bapi import *
from util.Logger import LOG

#############################################################################

COIN = 'BTCUSDT'

#############################################################################

# Grouping Price
def convert_round(x, grouping=8):
    return [int(int(float(x[0])) / grouping) * grouping, float(x[1])]


if __name__ == '__main__':

    print('Main Start')

    #############################################################################
    # 바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
    client = getClient()
    assert client

    server_time_sync(client)

    #############################################################################
 
    # API제한 체크
    if check_api_limit(client):
        print('sleep...')
        time.sleep(60)


    # 최소 매매 자금 체크
    wallet_size = get_asset_balance(client)
    LOG.info(f'현재 가지고 있는 USDT: {wallet_size}')
    
    if wallet_size < get_require_minsize(client, COIN):
        LOG.info(f'{COIN} 를 매매할 돈이 부족합니다.')
        exit() 


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
