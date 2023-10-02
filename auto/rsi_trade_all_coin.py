# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import os
Join = os.path.join

from apscheduler.schedulers.background import BackgroundScheduler

import pprint
import time
from db import SQLite
from query import *

import ta
import pandas as pd
import numpy as np
np.set_printoptions(suppress=True)

from tqdm import tqdm
from bapi import *
from utils import *
from Logger import LOG

try: import simplejson as json
except ImportError: import json

#############################################################################

DB_CONFIG = {'database': r'var/database.db'}

#############################################################################

def drop_table():
    conn = SQLite(DB_CONFIG)
    conn.query('DROP TABLE binance;')
    conn.query('DROP TABLE trade;')
    conn.close()


def create_database():
    conn = SQLite(DB_CONFIG)

    conn.query(query_create_symbol_table)
    conn.query(query_create_trade_table)

    if conn.query('select exists(select * from trade);')[0][0] == 0:
        # RSI 1시간봉 기준
        # RSI 윈도우 사이즈 기본이 14
        conn.query(query_insert_trade_base_data, (0,0,Client.KLINE_INTERVAL_1HOUR,21,15,2))

    conn.close()


#############################################################################

def get_rsi(symbol):
    # 현재 캔들 정보를 가져옵니다.

    conn = SQLite(DB_CONFIG)
    kline_interval, rsi_window = conn.query(query_get_rsi_set)[0]
    conn.close()

    candles = client.get_klines(symbol=symbol,
                                interval=kline_interval,
                                limit=250)

    # 데이터 프레임 생성
    df = pd.DataFrame(candles)
    # 불필요한 컬럼 정리
    df.drop(df.loc[:, 7:11], axis=1, inplace=True)

    df = df.astype(float)
    df.columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime']

    try:
        rsi = ta.momentum.RSIIndicator(close=df['Close'], window=rsi_window).rsi()
        return np.round(rsi.loc[249], 2)

    except KeyError:
        return 50           # 상장 기간이 짧아 데이터가 부족한 코안


def get_fluctuation_rate(client, symbol):
    klines = get_historical_klines_hour(client, symbol, 24)
    return (pd.DataFrame(klines)[4].astype(float).pct_change() + 1).prod() - 1
    

#############################################################################

def update_symbol_data(client):
    LOG.info('심볼 데이터 초기화 및 업데이트')

    conn = SQLite(DB_CONFIG)
    for info in get_exchange_info_usdt(client):
        symbol      = info.get('symbol')
        tick_size   = get_require_tick_size(info)
        step_size   = get_require_min_step_size(info)
        min_lot     = get_require_min_lot(info)
        min_noti    = get_require_min_notional(info)

        param = (symbol, tick_size, step_size, min_lot, min_noti, None, 'BUY_ORDER_MONITOR')
        conn.query(query_insert_symbol_table, param)


    conn.query(query_update_init_time, (get_today(),))
    conn.close()


#############################################################################

def find_rsi(client):

    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_all_symbol)

    # 5분마다 RSI 계산
    LOG.info('코인 RSI 계산 중...')
    for symbol in tqdm(rows):
        symbol = symbol[0]
        
        rsi = get_rsi(symbol)
        conn.query(query_update_rsi, (rsi, symbol))

    # 최종 RSI 계산 시간 기록
    conn.query(query_update_rsi_time, (get_today(),))
    
    p, count = check_api_limit(client)
    LOG.info(f'RSI - API LIMIT 확인###{count}')


#############################################################################


def buy_logic(client, symbol):
    print(f'{symbol}#start buy logic')

    try:
        conn = SQLite(DB_CONFIG)
        alpha_qty, trade_qty = conn.query(query_get_trade_set)[0]

        # 최소 매수 수량 구하기
        qty = get_require_min_qty(client, symbol, alpha_qty) * trade_qty

        if order_market_buy(client, symbol, qty):
            conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))

    except Exception as e:
        LOG.info(f'매수로직실패:#{symbol}#{e}')

    finally:
        conn.close()



def sell_logic(client, symbol):
    print(f'{symbol}#start sell logic')

    try:
        conn = SQLite(DB_CONFIG)
        qty = sell_asset_balance(client, symbol)

        if order_market_sell(client, symbol, qty):
            conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))

    except Exception as e:
        LOG.info(f'매도로직실패:#{symbol}#{e}')

    finally:
        conn.close()

#############################################################################

def init_symbol_data(client):

    #바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
    #server_time_sync(client)

    # 현재 USDT 자금 체크
    LOG.info(f'현재 가지고 있는 USDT: {get_asset_balance(client)}')


    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_init_time)
    conn.close()
    
    # 최초 등록
    if rows is False:
        LOG.info('테이블 생성')
        drop_table()
        create_database()
        update_symbol_data(client)

    find_rsi(client)

    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Seoul')
    scheduler.add_job(find_rsi, 'interval', minutes=1, id="find_rsi", args=(client,))
    scheduler.start()


#############################################################################


if __name__ == '__main__':

    print('Main Start')

    # 클라이언트 셋팅
    client = getClient()
    assert client

    #############################################################################

    init_symbol_data(client)


    # 트레이딩인 RSI을 가져와서 조건에 맞는 코인은 매수 로직 태우기
    while True:
        
        # 오더북 전체 루프 시작
        conn = SQLite(DB_CONFIG)
        rows = conn.query(query_get_symbol_info)
        conn.close()

        LOG.info('트레이딩 시작')


        for row in rows:
            symbol, rsi, status = row

            #LOG.info(f'트레이드 시작#{symbol}###{rsi}###{status}')
         
            if status == 'BUY_ORDER_MONITOR':   #매수 조건이 이루어지기 위한 모니터링
                if rsi < 30 and get_asset_balance(client) > 25:
                    buy_logic(client, symbol)

            elif status == 'SELL_ORDER_MONITOR':   #매도 조건이 이루어지기 위한 모니터링
                if rsi >= 70:
                    sell_logic(client, symbol)

            time.sleep(0.3)


        p, count = check_api_limit(client)
        LOG.info(f'Main - API LIMIT 확인###{count}')
        time.sleep(60*1)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################

