# -*- coding:utf-8 -*-

#############################################################################

from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

import warnings
warnings.filterwarnings("ignore")

import os
Join = os.path.join

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

KLINE_INTERVAL = Client.KLINE_INTERVAL_1HOUR            # RSI 1시간봉 기준
WINDOWS = 21                                            # RSI 윈도우 사이즈 기본이 14

DB_CONFIG = {'database': r'var/database.db'}

#############################################################################

def drop_table():
    conn = SQLite(DB_CONFIG)
    conn.query('DROP TABLE binance;')
    conn.query('DROP TABLE trade;')
    conn.query('DROP TABLE rate;')
    conn.query('DROP TABLE total_rate;')
    conn.query('DROP TABLE api_limit;')
    conn.close()


def create_database():
    conn = SQLite(DB_CONFIG)

    conn.query(query_create_symbol_table)
    conn.query(query_create_trade_table)
    conn.query(query_create_rate_table)
    conn.query(query_create_total_rate_table)
    conn.query(query_create_api_limit_table)

    if conn.query('select exists(select * from trade);')[0][0] == 0:
        conn.query(query_insert_trade_base_data, (0,0,0,0))

    conn.close()


#############################################################################

def get_rate_of_return(client, symbol):

    conn = SQLite(DB_CONFIG)
    agg_trades = get_my_trades(client, symbol=symbol,
                                startTime=kst_to_utc(get_today_midnight()))


    initial_values = list()
    final_values = list()

    for trade_info in agg_trades:
        ids         = trade_info.get('id')
        t           = trade_info.get('time')
        qty         = float(trade_info.get('qty'))
        quoteQty    = float(trade_info.get('quoteQty'))
        price       = float(trade_info.get('price'))
        commission  = float(trade_info.get('commission'))
        buyer       = 'buy' if trade_info.get('isBuyer') else 'sell'       

        if trade_info.get('isBuyer'):
            initial_values.append(quoteQty / qty)
        else:
            final_values.append(quoteQty / qty)

        param = (ids,utc_to_kst(t),symbol,qty,quoteQty,price,commission,buyer)
        conn.query(query_insert_rate_table, param)


    initial_values = sum(initial_values)
    final_values = sum(final_values)

    return_tate = ((final_values - initial_values) / initial_values)*100
    conn.query(query_insert_total_rate_table, (get_today_midnight().split('T')[0],symbol,np.round(return_tate, 2)))



    conn.close()

#############################################################################

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

    rsi = ta.momentum.RSIIndicator(close=df['Close'], window=WINDOWS).rsi()

    return np.round(rsi.loc[249], 2)


def get_fluctuation_rate(client, symbol):
    klines = get_historical_klines_hour(client, symbol, 24)
    return (pd.DataFrame(klines)[4].astype(float).pct_change() + 1).prod() - 1
    

#############################################################################

def update_symbol_data(client):
    LOG.info('심볼 데이터 초기화 및 업데이트')

    conn = SQLite(DB_CONFIG)
    conn.query(query_init_symbol_table)

    for info in get_exchange_info_usdt(client):
        symbol      = info.get('symbol')
        tick_size   = get_require_tick_size(info)
        step_size   = get_require_min_step_size(info)
        min_lot     = get_require_min_lot(info)
        min_noti    = get_require_min_notional(info)

        param = (symbol, None, None, 0, tick_size, step_size, min_lot, min_noti, None, None, 'BUY_ORDER_MONITOR')
        conn.query(query_insert_symbol_table, param)


    LOG.info('API 제한수 업데이트')
    for info in get_exchange_info_api(client):
        interval = info.get('interval')
        intervalNum = info.get('intervalNum')
        limit = info.get('limit')
        rateLimitType = info.get('rateLimitType')

        param = (interval, intervalNum, limit, rateLimitType)
        conn.query(query_insert_api_limit_table, param)


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
    LOG.info(f'API LIMIT 확인###{count}')



def find_top_coin(client):

    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_all_symbol)

    # 4시간마다 모든 코인의 등락율 계산
    luctuation_rates, symbols = list(), list()

    LOG.info('코인 등락율 계산 중...')
    for symbol in tqdm(rows):
        symbol = symbol[0]

        # 등락율 계산
        luctuation_rate = get_fluctuation_rate(client, symbol)
        conn.query(query_update_luctuation_rate,                                \
                    (np.round(luctuation_rate*100, 2), symbol))

        symbols.append(symbol)
        luctuation_rates.append(luctuation_rate)


    # 최종 등락율 계산 시간 기록
    conn.query(query_update_luctuation_rate_time, (get_today(),))
    conn.close()

    p, count = check_api_limit(client)
    LOG.info(f'API LIMIT 확인###{count}')



def init_wait_time(client):

    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_order_wait_time_count)

    # 최송 수익률 계산
    LOG.info('최종 수익률 계산')
    for row in rows:
        symbol = row[0]
        get_rate_of_return(client, symbol)

        # API 가중치가 높은 쿼리임 (20)
        time.sleep(1)

        conn.query(query_update_order_wait_time, (0, symbol))

    conn.close()

#############################################################################


def buy_logic(client, symbol):
    print(f'{symbol}#start buy logic')

    try:  
        if order_market_buy(client, symbol, alpha_qty=15):
            conn = SQLite(DB_CONFIG)
            conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
            conn.close()

    except Exception as e:
        LOG.info(f'매수로직실패:#{symbol}#{e}')

    finally:
        conn.close()



def sell_logic(client, symbol):
    print(f'{symbol}#start sell logic')

    try:
        conn = SQLite(DB_CONFIG)
        order_market_sell(client, symbol)
        conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))

        # 매수/매도가 이루어졌다는걸 카운팅 표시
        wait_time = conn.query(query_get_order_wait_time, (symbol,))[0][0] + 1
        conn.query(query_update_order_wait_time, (wait_time, symbol))

        conn.close()

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
    find_top_coin(client)
    init_wait_time(client)


    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Seoul')
    scheduler.add_job(find_top_coin, 'interval', hours=4, id="top_coin", args=(client,))
    scheduler.add_job(find_rsi, 'interval', minutes=1, id="find_rsi", args=(client,))
    scheduler.add_job(init_wait_time, 'interval', hours=1, id='init_wait_time', args=(client,))
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
            symbol, buy_orderId, sell_orderId, rsi, status = row

            #LOG.info(f'트레이드 시작#{symbol}###{rsi}###{status}')
         
            if status == 'BUY_ORDER_MONITOR':   #매수 조건이 이루어지기 위한 모니터링
                if rsi < 25 and get_asset_balance(client) > 10:
                    buy_logic(client, symbol)

            elif status == 'SELL_ORDER_MONITOR':   #매도 조건이 이루어지기 위한 모니터링
                if rsi >= 70:
                    sell_logic(client, symbol)

            time.sleep(0.3)


        time.sleep(60*1)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################

