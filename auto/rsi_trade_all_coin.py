# -*- coding:utf-8 -*-

#############################################################################

from threading import Thread
import threading

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

KLINE_INTERVAL = Client.KLINE_INTERVAL_15MINUTE
WINDOWS = 7

TOP_COIN_CHOICE = 'HIGHT'
MONITORING_COIN_NUMBOR = 5

event = threading.Event()

DB_CONFIG = {'database': r'var/database.db'}

#############################################################################

def drop_table():
    conn = SQLite(DB_CONFIG)
    conn.query('DROP TABLE symbol;')
    conn.query('DROP TABLE trade;')
    conn.close()


def create_database():
    conn = SQLite(DB_CONFIG)

    conn.query(query_create_symbol_table)
    conn.query(query_create_trade_table)

    if conn.query('select exists(select * from trade);')[0][0] == 0:
        conn.query(query_insert_trade_base_data, (0,0,0,0))

    conn.close()


def init_env():

    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_init_time)
    conn.close()

    if rows is False:
        LOG.info('테이블 생성')
        create_database()


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
    klines = get_historical_klines_1hour(client, symbol)
    return (pd.DataFrame(klines)[4].astype(float).pct_change() + 1).prod() - 1
    

# 인기 있는 상위 코인 선정
def find_top_coin(client):
    
    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_symbol_table)


    # 1시간마다 모든 코인의 등락율 계산
    luctuation_rates, symbols = list(), list()

    if time_check('luctuation_rate_time', 'hours', 1) is False:
        LOG.info('코인 등락율 계산 중...')
        for symbol in tqdm(rows):
            symbol = symbol[0]

            # 모든 코인 대기 상태로 변경
            conn.query(query_update_status, ('WAIT', symbol))

            # 등락율 계산
            luctuation_rate = get_fluctuation_rate(client, symbol)
            conn.query(query_update_luctuation_rate,                                \
                        (np.round(luctuation_rate*100, 2), symbol))

            symbols.append(symbol)
            luctuation_rates.append(luctuation_rate)


        top_coin = pd.DataFrame(luctuation_rates, index=symbols, columns=['rate'])


        # 상위 코인 30개 가져오기
        if TOP_COIN_CHOICE == 'HIGHT':
            for symbol, rate in top_coin.rate.nlargest(MONITORING_COIN_NUMBOR).iteritems():
                conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))

        
        elif TOP_COIN_CHOICE == 'LOW':
            for symbol, rate in top_coin.rate.nsmallest(MONITORING_COIN_NUMBOR).iteritems():
                conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))


        # 최종 등락율 계산 시간 기록
        conn.query(query_update_luctuation_rate_time, (get_today(),))

    conn.close()



def find_rsi(client):

    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_symbol_buy_monitor)

    # 5분마다 RSI 계산
    rsi_log  = '현재 RSI와 심볼: '
    if time_check('rsi_time', 'minutes', 5) is False:
        LOG.info('코인 RSI 계산 중...')
        for symbol in rows:
            symbol = symbol[0]
            
            rsi = get_rsi(symbol)
            conn.query(query_update_rsi, (rsi, symbol))

            rsi_log += f'{symbol}#{rsi}  '
        
        LOG.info(f'{rsi_log}')

        # 최종 RSI 계산 시간 기록
        conn.query(query_update_rsi_time, (get_today(),))

    conn.close()
 

#############################################################################

def update_symbol_data(client):
    LOG.info('기존 심볼 데이터 초기화 및 업데이트')

    conn = SQLite(DB_CONFIG)
    conn.query(query_init_symbol_table)

    for info in get_exchange_info_usdt(client):
        symbol      = info.get('symbol')
        tick_size   = get_require_tick_size(info)
        step_size   = get_require_min_step_size(info)
        min_lot     = get_require_min_lot(info)
        min_noti    = get_require_min_notional(info)

        param = (symbol, None, None, tick_size, step_size, min_lot, min_noti, None, None, 'WAIT')
        conn.query(query_insert_symbol_table, param)
    
    conn.query(query_update_rsi_time, (0,))
    conn.query(query_update_luctuation_rate_time, (0,))
    conn.query(query_update_init_time, (get_today(),))
    
    conn.close()


def set_order(client):
    # 오더북 체크
    LOG.info('오더북을 확인합니다.')
    conn = SQLite(DB_CONFIG)

    for info in get_open_orders(client):
        if info.get('side') == 'BUY' and info.get('status') == ORDER_STATUS_NEW:
            symbol      = info.get('symbol')
            rsi         = get_rsi(info.get('symbol'))
            buy_orderId = info.get('orderId')

            # RSI가 30이상이면 buy 주문 유지 할필요 없기 때문에 취소한다.
            if rsi > 30:
                LOG.info(f'{symbol}:RSI 오버로 주문을 취소합니다.')
                cancle_order(client, symbol, buy_orderId)
                conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))
            else:
                # 주문을 취소하지 않고 유지한다.
                LOG.info(f'{symbol}:BUY 주문번호 저장')
                conn.query(query_update_buy_orderId, (buy_orderId, symbol))
                conn.query(query_update_status, ('BUY_ORDER_EXECUTE_WAIT', symbol))

    
        elif info.get('side') == 'SELL' and info.get('status') == ORDER_STATUS_NEW:
            symbol       = info.get('symbol')
            rsi          = get_rsi(info.get('symbol'))
            sell_orderId = info.get('orderId')


            # RSI가 70이하면 sell 주문 유지 할필요 없기 때문에 취소한다.
            if rsi < 70:
                LOG.info(f'{symbol}:RSI 오버로 주문을 취소합니다.')
                cancle_order(client, symbol, sell_orderId)
                conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
            else:
                LOG.info(f'{symbol}:SELL 주문번호 저장')
                conn.query(query_update_sell_orderId, (sell_orderId, symbol))
                conn.query(query_update_status, ('SELL_ORDER_EXECUTE_WAIT', symbol))

    conn.close()


def set_has_coin(client):
    # 코인 체크
    LOG.info('매수한 코인을 확인합니다.')
    conn = SQLite(DB_CONFIG)

    # 현재 가지고 있는 코인이 매매 최소 수량보다 크다면 판매가 가능하므로 SELL 로직으로 넘긴다.
    for info in client.get_account().get('balances'):
        money = float(info.get('free'))
        symbol = info.get('asset')

        if (money > 0) and (symbol != 'USDT' and symbol != 'BNB'):
            symbol += 'USDT'
            min_qty = get_require_min_qty(client, symbol, alpha_qty=5)
            
            if money >= min_qty:
                LOG.info(f'Sell 모니터링 시작:{symbol}###{money}###{min_qty}')
                conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
            else:
                #LOG.info(f'코인 부족###보유코인###요구코인:{symbol}###{money}###{min_qty}')
                pass


    conn.close()



def init_symbol_data(client):

    #바이낸스 클라이언트 인스턴스 생성과 서버 시간 동기화
    #server_time_sync(client)

    # 현재 USDT 자금 체크
    LOG.info(f'현재 가지고 있는 USDT: {get_asset_balance(client)}')


    # 프로그램 재시작 동안 RSI, 등가율이 변화할 수도 있기 때문에 모든 심볼 데이터를 초기화 시킨다.
    # 이미 매매한 코인만 trading 시킨다. 
    update_symbol_data(client)

    find_top_coin(client)
    find_rsi(client)

    set_order(client)
    set_has_coin(client)

#############################################################################


def loop_find_coin(client):

    while True:

        # 모니터링 할 코인 찾기
        find_top_coin(client)

        # RSI 전부 계산
        find_rsi(client)

        # find_top_coin함수에서 상태 값들을 초기화 하였기 때문에 매매한 코인들은 찾아서 진행한다.
        set_order(client)
        set_has_coin(client)

        conn = SQLite(DB_CONFIG)
        rows = conn.query(query_get_symbol_buy_monitor)

        sum_noti = 0
        for symbol in rows:
            symbol = symbol[0]

            sum_noti += get_size(symbol, 'min_noti')


        conn.query(query_update_sum_noti, (sum_noti,))
        conn.close()

        event.set()

        LOG.info(f'모니터링 할 코인 5분 대기')
        time.sleep(60*5)


#############################################################################


def buy_logic(client, symbol, buy_order_id=None):
    print(f'{symbol}#start buy logic')
    #############################################################################
    # 매수 로직
    #############################################################################
    buy_log_cnt = 0

    while True:
        try:
            # 매수된 코인이 없기 때문에 매수 주문서 접수 대기
            if buy_order_id is None:
                buy_order_id = order_buy(client, symbol)
                
                conn = SQLite(DB_CONFIG)
                conn.query(query_update_buy_orderId, (buy_order_id,))
                conn.query(query_update_status, ('BUY_ORDER_EXECUTE_WAIT', symbol))
                conn.close()


            # 신규 매수 주문 접수가 완료 되었고 매수 체결이 이루어 졌는지 확인 해야한다.
            elif buy_order_id is not None:
                order_status = get_order_status(client, symbol, buy_order_id)
                
                # 매수 주문이 체결될 때까지 대기
                if order_status == ORDER_STATUS_NEW:
                    continue

                # 이전에 접수 되었던 예약 매수 주문이 취소되었거나 유효기간이 지나면 다시 예약 매수 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    LOG.info(f'{symbol}#매수 주문 접수가 취소. 신규 매수 주문 접수를 대기')
                    
                    conn = SQLite(DB_CONFIG)
                    conn.query(query_update_buy_orderId, (None,))
                    conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))
                    conn.close()

                    return


                # 주문이 체결된 상태이며, 매도 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    LOG.info(f'{symbol}#매수 주문 체결 완료')
                    conn = SQLite(DB_CONFIG)
                    conn.query(query_update_buy_orderId, (None,))
                    conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
                    conn.close()
                    
                    return


        except Exception as e:
            LOG.info(f'매수로직실패:#{symbol}#{e}')


        if buy_log_cnt == 180:
            cancle_order(client, symbol, buy_order_id)
            conn.query(query_update_buy_orderId, (None,))
            conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))
            LOG.info(f'{symbol}#15분째 매수 주문이 체결이 안되서 주문을 취소')

            return

        else:
            buy_log_cnt += 1
            time.sleep(5)



def sell_logic(client, symbol, order_book, sell_order_id=None):
    print(f'{symbol}#start sell logic')
    #############################################################################
    # 매도 로직
    #############################################################################
    sell_log_cnt = 0

    while True:
        try:
            # 매도된 코인이 없기 때문에 매도 주문서 접수 대기
            if sell_order_id is None:
                sell_order_id = order_sell(client, symbol, order_book)

                conn = SQLite(DB_CONFIG)
                row = conn.query(query_update_sell_orderId, (sell_order_id,))
                row = conn.query(query_update_status, ('SELL_ORDER_EXECUTE_WAIT', symbol))
                conn.close()
   

            # 신규 매도 주문 접수가 완료 되었고 매도 체결이 이루어 졌는지 확인 해야한다.
            elif sell_order_id is not None:
                order_status = get_order_status(client, symbol, sell_order_id)
                
                # 매도 주문이 체결될 때까지 대기
                if order_status == ORDER_STATUS_NEW:
                    continue
                    

                # 이전에 접수 되었던 예약 매도 주문이 취소되었거나 유효기간이 지나면 다시 예약 매도 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    LOG.info(f'{symbol}#매도 주문 접수가 취소. 신규 매도 주문 접수를 대기')
                    
                    conn = SQLite(DB_CONFIG)
                    conn.query(query_update_sell_order_id, (None,))
                    conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
                    conn.close()

                    return


                # 매도 주문이 체결된 상태이며, 다시 매수 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    LOG.info(f'{symbol}#매도 주문 체결이 완료')
                    conn = SQLite(DB_CONFIG)
                    conn.query(query_update_sell_orderId, (None,))
                    conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))
                    conn.close()
                    
                    return

        except Exception as e:
           LOG.info(f'매도로직실패:#{symbol}#{e}')

        if sell_log_cnt == 180:
            cancle_order(client, symbol, sell_order_id)
            conn.query(query_update_sell_orderId, (None,))
            conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
            LOG.info(f'{symbol}#15분째 매도 주문이 체결이 안되서 주문을 취소')
            
            return

        else:
            sell_log_cnt += 1
            time.sleep(5)


#############################################################################


if __name__ == '__main__':

    print('Main Start')

    # 클라이언트 셋팅
    client = getClient()
    assert client

    #############################################################################

    #drop_table()
    init_env()
    init_symbol_data(client)

    # 등락율 계산과 RSI 계산
    find_coin_thread = Thread(target=loop_find_coin, args=(client,))
    find_coin_thread.daemon = True
    find_coin_thread.start()
 

    # 트레이딩인 RSI을 가져와서 조건에 맞는 코인은 매수 로직 태우기
    while True:
        event.wait()
        
        # 오더북 전체 루프 시작
        conn = SQLite(DB_CONFIG)
        rows = conn.query(query_get_symbol_info)
        conn.close()

        LOG.info('트레이딩 시작')
        for row in rows:
            symbol, buy_orderId, sell_orderId, rsi, status = row

            LOG.info(f'트레이드 시작#{symbol}###{status}')
                        
            if status == 'BUY_ORDER_MONITOR':   #매수 조건이 이루어지기 위한 모니터링
                if rsi < 30:
                    sell_thread = Thread(target=buy_logic, args=(client, symbol))
                    sell_thread.daemon = True
                    sell_thread.start()

            elif status == 'BUY_ORDER_EXECUTE_WAIT':   #매수 주문 체결 대기
                sell_thread = Thread(target=buy_logic, args=(client, symbol, buy_orderId,))
                sell_thread.daemon = True
                sell_thread.start()

            elif status == 'SELL_ORDER_MONITOR':   #매도 조건이 이루어지기 위한 모니터링
                if rsi >= 70:
                    sell_thread = Thread(target=sell_logic, args=(client, symbol))
                    sell_thread.daemon = True
                    sell_thread.start()

            elif status == 'SELL_ORDER_EXECUTE_WAIT':   #매도 주문 체결 대기
                sell_thread = Thread(target=sell_logic, args=(client, symbol, sell_orderId,))
                sell_thread.daemon = True
                sell_thread.start()

            time.sleep(1)


        # 15분정도 루프
        LOG.info(f'오더북 트레이드 5분 대기')        
        time.sleep(60*5)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
