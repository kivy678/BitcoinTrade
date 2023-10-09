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
from upbit_api import *
from utils import *
from Logger import LOG

try: import simplejson as json
except ImportError: import json

#############################################################################

DB_CONFIG = {'database': r'var/database.db'}

#############################################################################

def drop_table():
    conn = SQLite(DB_CONFIG)
    conn.query('DROP TABLE upbit;')
    conn.query('DROP TABLE trade;')
    conn.close()


def create_database():
    conn = SQLite(DB_CONFIG)

    conn.query(query_create_symbol_table)
    conn.query(query_create_trade_table)

    if conn.query('select exists(select * from trade);')[0][0] == 0:
        # RSI 1시간봉 기준
        # RSI 윈도우 사이즈 기본이 14
        conn.query(query_insert_trade_base_data, (0,0,60,21,0.2))

    conn.close()

#############################################################################

def get_rsi(symbol):
    # 현재 캔들 정보를 가져옵니다.

    conn = SQLite(DB_CONFIG)
    kline_interval, rsi_window = conn.query(query_get_rsi_set)[0]
    conn.close()

    df = pd.DataFrame(get_historical_klines(symbol, kline_interval, 200))
    df.index.name = 'id'

    df.drop(df.iloc[:, 0:2], axis=1, inplace=True)
    df.drop(df.loc[:, ['timestamp', 'candle_acc_trade_price', 'unit']], axis=1, inplace=True)

    df = df.rename(columns={'candle_date_time_kst': 'OpenTime',
                            'opening_price': 'Open', 
                            'high_price': 'High',
                            'low_price': 'Low',
                            'trade_price': 'Close',
                            'candle_acc_trade_volume': 'Volume'
                            })

    df = df.sort_values(by='OpenTime', ascending=True)
    df['Close'] = df['Close'].astype(float)

    try:
        rsi = ta.momentum.RSIIndicator(close=df['Close'], window=rsi_window).rsi()
        return np.round(rsi.loc[0], 2)

    except KeyError:
        return 50           # 상장 기간이 짧아 데이터가 부족한 코안   

#############################################################################

def update_symbol_data():
    LOG.info('심볼 데이터 초기화 및 업데이트')

    conn = SQLite(DB_CONFIG)
    for symbol in get_all_coin():
        state, min_total = get_exchange_info(symbol)

        if state == 'active':
            param = (symbol, min_total, None, 'BUY_ORDER_MONITOR')
            conn.query(query_insert_symbol_table, param)

        time.sleep(0.1)


    conn.query(query_update_init_time, (get_today(),))
    conn.close()

#############################################################################

def find_rsi():

    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_all_symbol)

    # 5분마다 RSI 계산
    LOG.info('코인 RSI 계산 중...')
    for symbol in tqdm(rows):
        symbol = symbol[0]
        
        rsi = get_rsi(symbol)
        conn.query(query_update_rsi, (rsi, symbol))
        time.sleep(0.1)


    # 최종 RSI 계산 시간 기록
    conn.query(query_update_rsi_time, (get_today(),))
    conn.close()


#############################################################################

def buy_logic(symbol):
    print(f'{symbol}#start buy logic')

    try:
        conn = SQLite(DB_CONFIG)

        min_noti = conn.query(query_get_size_symbol, (symbol,))[0][0]
        trade_qty = conn.query(query_get_trade_set)[0][0]

        qty = min_noti + (min_noti * trade_qty)

        if order_market_buy(symbol, qty):
            conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))

    except Exception as e:
        LOG.info(f'매수로직실패:#{symbol}#{e}')

    finally:
        conn.close()


def sell_logic(symbol):
    print(f'{symbol}#start sell logic')

    try:
        conn = SQLite(DB_CONFIG)
        qty = get_asset_balance(symbol)

        if order_market_sell(symbol, qty):
            conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))

    except Exception as e:
        LOG.info(f'매도로직실패:#{symbol}#{e}')

    finally:
        conn.close()

#############################################################################

def init_symbol_data():

    # 현재 KRW 자금 체크
    LOG.info(f'현재 가지고 있는 KRW: {get_asset_balance("KRW")}')


    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_init_time)
    conn.close()
    
    # 최초 등록
    if rows is False:
        LOG.info('테이블 생성')
        drop_table()
        create_database()
        update_symbol_data()


    find_rsi()

    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Seoul')
    scheduler.add_job(find_rsi, 'interval', minutes=1, id="find_rsi", args=(,))
    scheduler.start()


#############################################################################


if __name__ == '__main__':

    print('Main Start')

    #############################################################################

    init_symbol_data()


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
                if rsi < 20 and get_asset_balance("KRW") > 10000:
                    buy_logic(symbol)

            if status == 'SELL_ORDER_MONITOR':   #매도 조건이 이루어지기 위한 모니터링
                if rsi >= 70:
                    sell_logic(symbol)

            time.sleep(0.1)

        LOG.info(f'Main - Sleep')
        time.sleep(60*1)


    #############################################################################

    print('Main End')

    #############################################################################

