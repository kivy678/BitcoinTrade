# -*- coding:utf-8 -*-

#############################################################################

from env import *

import hashlib
import jwt
import requests
import uuid
from urllib.parse import urlencode, unquote

from query import *
from Logger import LOG

from db import SQLite

#############################################################################

server_url = 'https://api.upbit.com'
DB_CONFIG = {'database': r'var/database.db'}

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


# 지갑에서 수량 가져오기
def get_asset_balance(symbol='KRW'):

    if symbol.endswith('KRW'):
        pass
    else:
        symbol = symbol.replace('KRW-', '')

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

        if currency == symbol:
            if float(balance) == 0:
                return 0

            elif float(balance) > 0.0001:
                return float(balance)


# 모든 코인 거래 정보 가져오기
# 레버리지 코인 제외, USDT로 거래, 트레이딩 가능
def get_exchange_info(symbol):
    
    params = {
      'market': symbol
    }
    query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")

    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    payload = {
        'access_key': UPBIT_ACCESS,
        'nonce': str(uuid.uuid4()),
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512'
    }

    jwt_token = jwt.encode(payload, UPBIT_SECRET)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
      'Authorization': authorization,
    }
    
    res = requests.get(server_url + f'/v1/orders/chance', params=params, headers=headers)
    rows = res.json()

    market = rows.get('market')
    min_total = market.get('ask')['min_total']
    state = market['state']

    _min, _sec = api_limit(res)

    return (state, min_total)


def get_all_coin():
    
    headers = {"accept": "application/json"}

    res = requests.get(server_url + '/v1/market/all?isDetails=false', headers=headers)

    for row in res.json():
        if row.get('market').startswith('KRW'):
            yield row.get('market')


#############################################################################

# 1시간 캔들 정보 가져오기
def get_historical_klines(symbol, m, count):

    headers = {"accept": "application/json"}

    # 가장 최신 시간순으로 정렬된다
    res     = requests.get(server_url + f'/v1/candles/minutes/{m}?market={symbol}&count={count}',
                            headers=headers)

    return res.json()

#############################################################################

def order_market_buy(symbol, price):
    params = {
        'market': symbol,
        'side': 'bid',
        'ord_type': 'price',
        'price': str(price)
    }

    query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")

    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    payload = {
    'access_key': UPBIT_ACCESS,
    'nonce': str(uuid.uuid4()),
    'query_hash': query_hash,
    'query_hash_alg': 'SHA512'
    }

    jwt_token = jwt.encode(payload, UPBIT_SECRET)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization,
    }

    try:
        res = requests.post(server_url + '/v1/orders', json=params, headers=headers)
        price = res.json().get('price')

        LOG.info(f'마켓 매수 주문 체결 완료: {symbol}##{price}')
        return True
    
    except Exception as e:
        LOG.info(f'마켓 매수 주문 실패 : {symbol}#{e}')
        return False


def order_market_sell(symbol, volume):
    params = {
        'market': symbol,
        'side': 'ask',
        'volume': str(volume),
        'ord_type': 'market'
    }

    query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")

    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    payload = {
    'access_key': UPBIT_ACCESS,
    'nonce': str(uuid.uuid4()),
    'query_hash': query_hash,
    'query_hash_alg': 'SHA512'
    }

    jwt_token = jwt.encode(payload, UPBIT_SECRET)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization,
    }

    try:
        res = requests.post(server_url + '/v1/orders', json=params, headers=headers)
        volume = res.json().get('volume')

        LOG.info(f'마켓 매도 주문 체결 완료: {symbol}##{volume}')
        return True
    
    except Exception as e:
        LOG.info(f'마켓 매도 주문 실패 : {symbol}#{e}')
        return False


#############################################################################
