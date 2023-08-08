# -*- coding:utf-8 -*-

#############################################################################

import time
from env import UPBIT_ACCESS, UPBIT_SECRET

from urllib.parse import urlencode, unquote
import jwt
import requests
import uuid

import ta
import pandas as pd
import numpy as np

#############################################################################

server_url = 'https://api.upbit.com'

#############################################################################


def api_limit(res):
    remain = res.headers['remaining-req'].split(';')
    for kv in remain:
        kv = kv.strip().split('=')
        if kv[0] == 'min':
            _min = kv[1]
        elif kv[0] == 'sec':
            _sec = kv[1]

    return (_min, _sec)


def get_assets(coin='KRW'):

    

    payload = {
        'access_key': UPBIT_ACCESS,
        'nonce': str(uuid.uuid4()),
    }

    jwt_token = jwt.encode(payload, UPBIT_SECRET)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
      'Authorization': authorization,
    }

    res = requests.get(server_url + '/v1/accounts', headers=headers)
    data = res.json()

    for row in data:
        currency = row.get('currency')
        balance  = row.get('balance')
        locked   = row.get('locked')

        if currency == coin:
            if float(balance) == 0:
                return 0

            elif float(balance) > 0.0001:
                return float(balance)


def get_all_coin():
    
    headers = {"accept": "application/json"}

    res = requests.get(server_url + '/v1/market/all?isDetails=false', headers=headers)

    return [row.get('market') for row in res.json()]



def get_candle(coin):
    headers = {"accept": "application/json"}

    res = requests.get(server_url + f'/v1/candles/minutes/30?market={coin}&count=14', headers=headers)
    df = pd.DataFrame(res.json())
    df.index.name = 'id'

    df.drop(df.iloc[:, 0:2], axis=1, inplace=True)
    df.drop(df.loc[:, ['timestamp', 'candle_acc_trade_price', 'unit']], axis=1, inplace=True)

    rsi = ta.momentum.RSIIndicator(close=df['trade_price'], window=14).rsi()

    return int(rsi.loc[13])




if __name__ == '__main__':

    print('Main Start')

    #balance = get_assets(coin='KRW')
    #print(balance)

    for coin in get_all_coin():
        rsi = get_candle(coin)
        print(coin, rsi)
        time.sleep(1)


    #############################################################################

    print('Main End')

    #############################################################################
