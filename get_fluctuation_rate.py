# -*- coding:utf-8 -*-

#############################################################################

from tqdm import tqdm
from env import *

import time
from binance import Client

import requests

import pandas as pd
import numpy as np

#############################################################################

server_url = 'https://api.upbit.com'

#############################################################################


def getClient():
    try:
        return Client(BINANCE_ACCESS, BINANCE_SECRET, {"verify": True, "timeout": 20})
    except BinanceAPIException as e:
        print(e)
        return False


def closeClient(client):
    try:
        client.close_connection()
    except BinanceAPIException as e:
        print(e)
        return False



def get_all_coin():
    
    headers = {"accept": "application/json"}

    res = requests.get(server_url + '/v1/market/all?isDetails=false', headers=headers)

    return [row.get('market') for row in res.json()]



def upbit_get_candle(coin):
    headers = {"accept": "application/json"}

    res = requests.get(server_url + f'/v1/candles/days?count=1&market={coin}', headers=headers)
    df = pd.DataFrame(res.json())

    change_rate = df['change_rate'][0].astype(float)*100

    return np.round(change_rate, 2)



def get_fluctuation_rate(client, symbol):
    klines = client.get_historical_klines(symbol,
                                            Client.KLINE_INTERVAL_1MINUTE,
                                           '1 day ago UTC')
    
    change_rate =  (pd.DataFrame(klines)[4].astype(float).pct_change() + 1).prod() - 1
    return np.round(change_rate*100, 2)



if __name__ == '__main__':

    print('Main Start')


    rate = upbit_get_candle('KRW-BTC')
    print(f'업비트 KRW-BTC 등락률: {rate}')
 


    client = getClient()
    assert client


    rate = get_fluctuation_rate(client, 'ETHUSDT')
    print(f'바이낸스 ETHUSDT 등락률: {rate}')


    cnt = 0
    coin_rate, coins = list(), list()
    for coin in tqdm(get_all_coin()):
        coin_rate.append(upbit_get_candle(coin))
        coins.append(coin)
        time.sleep(1)

        if cnt == 30:
            break
        else:
            cnt += 1

        
    top_coin = pd.DataFrame(coin_rate, index=coins, columns=['rate'])
    for coin, rate in top_coin.rate.nlargest(30).iteritems():
        print(coin, rate)



    #############################################################################

    print('Main End')

    #############################################################################
