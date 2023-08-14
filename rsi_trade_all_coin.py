# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import os
Join = os.path.join

import pprint
import time
import ta
import pandas as pd
import numpy as np
np.set_printoptions(suppress=True)

from tqdm import tqdm
from util.utils import *
from util.bapi2 import *
from util.Logger import LOG

try: import simplejson as json
except ImportError: import json

#############################################################################

KLINE_INTERVAL = Client.KLINE_INTERVAL_15MINUTE
SYMBOL_PATH    = Join('var', 'symbol.txt')
TRADING_PATH   = Join('var', 'trade.txt')

exclude_coin   = ['UP', 'DOWN', 'BEAR', 'BULL'] # 레버리지 코인

MONITORING_COIN = 30

#############################################################################


def time_check(j, k, f):
    t = j.get(k)
    
    if t:
        return False if is_passed_time(t, f) is True else True

    else:
        return False



def load_file(path):
    with open(path, 'r', encoding='utf-8-sig') as fr:
        return json.load(fr)


def save_file(path, data):
    with open(path, 'w', encoding='utf-8') as fw:
        json.dump(data, fw, indent=4, separators=(',', ': '))


def init_trade(client):

    order_book = {}
    trade_system = {}

    #바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
    server_time_sync(client)

    # 현재 USDT 자금 체크
    LOG.info(f'현재 가지고 있는 USDT: {get_asset_balance(client)}')


    # 최초 심볼 등록 및 파일 저장
    if not os.path.exists(SYMBOL_PATH):
        LOG.info('init order_book')
        for info in get_exchange_info_usdt(client):
            symbol      = info.get('symbol')
            tick_size   = get_require_tick_size(info)
            step_size   = get_require_min_step_size(info)
            min_lot     = get_require_min_lot(info)
            min_noti    = get_require_min_notional(info)

            order_book.update({symbol: {'buy_orderId':      None,
                                        'sell_orderId':     None,
                                        'tick_size':        tick_size,
                                        'step_size':        step_size,
                                        'min_lot':          min_lot,
                                        'min_noti':         min_noti,
                                        'luctuation_rate':  None,
                                        'trading':          False,
                                        'rsi': 50}})

            trade_system['init_time'] = get_today()

    else:
        # 이미 저장되어 있으면 파일 로드
        LOG.info('load order_book')
        order_book      = load_file(SYMBOL_PATH)
        trade_system    = load_file(TRADING_PATH)
        
        for symbol in order_book:
            order_book[symbol]['buy_orderId']    = None
            order_book[symbol]['sell_orderId']   = None
            order_book[symbol]['rsi']            = 50


    # 오더북 체크
    for info in get_open_orders(client):
        if info.get('side') == 'BUY' and info.get('status') == ORDER_STATUS_NEW:
            order_book[info.get('symbol')]['buy_orderId'] = info.get('orderId')

        elif info.get('side') == 'SELL' and info.get('status') == ORDER_STATUS_NEW:
            order_book[info.get('symbol')]['sell_orderId'] = info.get('orderId')
            

    # 파일로 저장
    LOG.info('save order_book')
    save_file(SYMBOL_PATH, order_book)
    save_file(TRADING_PATH, trade_system)

    return order_book, trade_system


def get_fluctuation_rate(client, symbol):
    klines = get_historical_klines_1hour(client, symbol)
    return (pd.DataFrame(klines)[4].astype(float).pct_change() + 1).prod() - 1
    

def get_rsi(symbol):
    # 현재 캔들 정보를 가져옵니다.
    candles = client.get_klines(symbol=symbol,
                                interval=KLINE_INTERVAL,
                                limit=250)

    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)

    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

    rsi = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()

    return np.round(rsi.loc[249], 2)


# 인기 있는 상위 코인 30개만 모니터링
def find_top_coin(client, order_book, trade_system):
    
    # 1시간마다 모든 코인의 등락율 계산
    if time_check(trade_system, 'luctuation_rate_time', 'hours') is False:
        LOG.info('코인 등락율 계산 중...')
        for symbol in tqdm(order_book):
            luctuation_rate = get_fluctuation_rate(client, symbol)
            order_book[symbol]['luctuation_rate'] = np.round(luctuation_rate*100, 2)
            #print(symbol, luctuation_rate)

        trade_system['luctuation_rate_time'] = get_today()


        # 트레이딩 정보 초기화
        for symbol in order_book:
            order_book[symbol]['trading'] = False
               
        
        # 상위 코인 30개 가져오기
        luctuation_rate, symbols = list(), list()
        for symbol in order_book:
            symbols.append(symbol)
            luctuation_rate.append(order_book.get(symbol).get('luctuation_rate'))

        top_coin = pd.DataFrame(luctuation_rate, index=symbols, columns=['rate'])

        for symbol, rate in top_coin.rate.nlargest(MONITORING_COIN).iteritems():
            order_book[symbol]['trading'] = True
        

        save_file(SYMBOL_PATH, order_book)
        save_file(TRADING_PATH, trade_system)



def find_rsi(client, order_book, trade_system):

    # 15분마다 RSI 계산
    if time_check(trade_system, 'rsi_time', 'minutes') is False:
        LOG.info('코인 RSI 계산 중...')
        for symbol in tqdm(order_book):
            if order_book.get(symbol).get('trading'):
                rsi = get_rsi(symbol)
                order_book[symbol]['rsi'] = rsi


        trade_system['rsi_time'] = get_today()

        save_file(SYMBOL_PATH, order_book)
        save_file(TRADING_PATH, trade_system)


if __name__ == '__main__':

    print('Main Start')

    # 클라이언트 셋팅
    client = getClient()
    assert client

    order_book, trade_system = init_trade(client)
    find_top_coin(client, order_book, trade_system)
    find_rsi(client, order_book, trade_system)




    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
