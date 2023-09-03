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

KLINE_INTERVAL = Client.KLINE_INTERVAL_15MINUTE         # RSI 15분봉기준
WINDOWS = 7                                             # RSI 윈도우 사이즈 기본이 14

TOP_COIN_CHOICE = 'HIGHT'
MONITORING_COIN_NUMBOR = 5


DB_CONFIG = {'database': r'var/database.db'}

#############################################################################

class TRADE_CANCLE(Exception): pass
class TRADE_WAIT(Exception): pass

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

        param = (utc_to_kst(t),symbol,qty,quoteQty,price,commission,buyer)
        conn.query(query_insert_rate_table, param)


    # 각 분할에 대한 수익률 계산
    profit_percentages = [((final - initial) / initial) * 100 for initial, final in zip(initial_values, final_values)]

    # 전체 수익률 계산
    return_tate = sum(profit_percentages)
    conn.query(query_insert_total_rate_table, (get_today_midnight(),symbol,return_tate))


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

        param = (symbol, None, None, 0, tick_size, step_size, min_lot, min_noti, None, None, 'WAIT')
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



def check_orderbook(client):
    # 오더북 체크 주문이 접수된 것들은 전부 취소, 오래된 주문일 가능성이 높고, 다시 가격을 정산하여 주문을 넣는게 낫다
    # RSI 가 너무 낮으면 코인도 정리한다.
    LOG.info('오더북을 확인합니다.')
    conn = SQLite(DB_CONFIG)

    for info in get_open_orders(client):
        if info.get('side') == 'BUY' and info.get('status') == ORDER_STATUS_NEW:
            symbol      = info.get('symbol')
            rsi         = get_rsi(info.get('symbol'))
            buy_orderId = info.get('orderId')

            LOG.info(f'{symbol}: 매수 주문을 취소합니다.')
            cancle_order(client, symbol, buy_orderId)
            conn.query(query_update_status, ('WAIT', symbol))

    
        elif info.get('side') == 'SELL' and info.get('status') == ORDER_STATUS_NEW:
            symbol       = info.get('symbol')
            rsi          = get_rsi(info.get('symbol'))
            sell_orderId = info.get('orderId')

            LOG.info(f'{symbol}:매도 주문을 취소합니다.')
            cancle_order(client, symbol, sell_orderId)
            conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))


    conn.close()


def check_has_coin(client):
    # 이미 매수 해서 매도해야할 코인들을 확인한다.
    LOG.info('매수한 코인을 확인합니다.')
    conn = SQLite(DB_CONFIG)


    # 가지고 있는 코인은 없는데 SELL_ORDER_MONITOR 로 오기입 된 코인 정리
    rows = conn.query(query_get_symbol_sell_monitor)
    for row in rows:
        symbol = row[0]
        if get_asset_balance(client, symbol=symbol) == 0:
            conn.query(query_update_status, ('WAIT', symbol))


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
                # 마켓가로 정리 시도해본다
                order_market_sell(client, symbol)
                conn.query(query_update_status, ('WAIT', symbol))


    conn.close()


#############################################################################


def find_rsi(client):

    conn = SQLite(DB_CONFIG)
    rows = conn.query(query_get_symbol_info)

    # 5분마다 RSI 계산
    rsi_log  = '현재 RSI와 심볼: '
    LOG.info('코인 RSI 계산 중...')
    for symbol in rows:
        symbol = symbol[0]
        
        rsi = get_rsi(symbol)
        conn.query(query_update_rsi, (rsi, symbol))

        rsi_log += f'{symbol}#{rsi}  '
    
    LOG.info(f'{rsi_log}')

    # 최종 RSI 계산 시간 기록
    conn.query(query_update_rsi_time, (get_today(),))

    # 매수할 코인들 USDT 요구 최소 총합
    rows = conn.query(query_get_symbol_buy_monitor)
    sum_noti = 0
    for symbol in rows:
        symbol = symbol[0]

        sum_noti += get_size(symbol, 'min_noti')


    conn.query(query_update_sum_noti, (sum_noti,))
    conn.close()
 


# 인기 있는 상위 코인 선정
def find_top_coin(client):
    LOG.info('코인 선정 시작')
    conn = SQLite(DB_CONFIG)

    rows = conn.query(query_get_symbol_info)

    # 최송 수익률 계산
    LOG.info('최종 수익률 계산')
    for row in rows:
        symbol, buy_orderId, sell_orderId, rsi, status = row
        get_rate_of_return(client, symbol)

        # API 가중치가 높은 쿼리임 (20)
        time.sleep(1)


    # 매수 모니터링한 코인들을 정리한다.
    LOG.info('기존 모니터링한 코인들 정리')
    for row in rows:
        symbol, buy_orderId, sell_orderId, rsi, status = row
        if status == 'BUY_ORDER_MONITOR':
            conn.query(query_update_status, ('WAIT', symbol))

        elif status == 'BUY_ORDER_EXECUTE_WAIT':
            cancle_order(client, symbol, buy_orderId)
            conn.query(query_update_status, ('WAIT', symbol))
            conn.query(query_update_order_id, (None, sell_orderId, symbol))

        else:
            # 이미 구입 했고 너무 낮은 RSI는 빨리 정리한다.
            if rsi is not None and rsi < 30:
                order_market_sell(client, symbol)
                conn.query(query_update_status, ('WAIT', symbol))
                conn.query(query_update_order_id, (None, None, symbol))


    # 매수가 가능한 (WAIT) 인 코인들 가져오기
    rows = conn.query(query_get_symbol_table)

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


    p, count = check_api_limit(client)
    LOG.info(f'API LIMIT 확인###{count}')
 

    # RSI도 추가로 계산해준다.
    find_rsi(client)


#############################################################################


def buy_logic(client, symbol, buy_order_id=None):
    print(f'{symbol}#start buy logic')
    #############################################################################
    # 매수 로직
    #############################################################################


    try:
        conn = SQLite(DB_CONFIG)

        # 매수된 코인이 없기 때문에 매수 주문서 접수 대기
        if buy_order_id is None:
            buy_order_id = order_limit_buy(client, symbol, alpha_price=2)
            conn.query(query_update_order_id, (buy_order_id, None, symbol))
            conn.query(query_update_status, ('BUY_ORDER_EXECUTE_WAIT', symbol))


        # 신규 매수 주문 접수가 완료 되었고 매수 체결이 이루어 졌는지 확인 해야한다.
        elif buy_order_id is not None:
            try:

                order_status = get_order_status(client, symbol, buy_order_id)

                # 4시간 지나면 주문 취소한다.
                if conn.query(query_get_order_wait_time, (symbol,))[0][0] > 10:#60*4:
                    raise TRADE_CANCLE('오래된 매수 주문 접수가 취소. 신규 매수 주문 접수를 대기')


                # 이전에 접수 되었던 예약 매수 주문이 취소되었거나 유효기간이 지나면 다시 예약 매수 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    raise TRADE_CANCLE('매수 주문 접수가 취소. 신규 매수 주문 접수를 대기')
                
                
                # 매수 주문이 체결될 때까지 대기
                elif order_status == ORDER_STATUS_NEW:
                    wait_time = conn.query(query_get_order_wait_time, (symbol,))[0][0] + 1
                    conn.query(query_update_order_wait_time, (wait_time, symbol))

                    LOG.info(f'주문대기###{symbol}###{wait_time}분')


                # 주문이 체결된 상태이며, 매도 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
                    conn.query(query_update_order_id, (None, None, symbol))
                    conn.query(query_update_order_wait_time, (0, symbol))

                    LOG.info(f'{symbol}###매수 주문 체결 완료')


            except TRADE_CANCLE as e:
                cancle_order(client, symbol, buy_orderId)
                conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))
                conn.query(query_update_order_id, (None, None, symbol))                
                conn.query(query_update_order_wait_time, (0, symbol))

                LOG.info(f'{symbol}###{e}')


    except Exception as e:
        LOG.info(f'매수로직실패:#{symbol}#{e}')

    finally:
        conn.close()



def sell_logic(client, symbol, sell_order_id=None):
    print(f'{symbol}#start sell logic')
    #############################################################################
    # 매도 로직
    #############################################################################

    try:
        conn = SQLite(DB_CONFIG)

        # 매도된 코인이 없기 때문에 매도 주문서 접수 대기
        if sell_order_id is None:
            sell_order_id = order_limit_sell(client, symbol, alpha_price=2)

            row = conn.query(query_update_order_id, (None, sell_order_id, symbol))
            row = conn.query(query_update_status, ('SELL_ORDER_EXECUTE_WAIT', symbol))


        # 신규 매도 주문 접수가 완료 되었고 매도 체결이 이루어 졌는지 확인 해야한다.
        elif sell_order_id is not None:
            try:
                order_status = get_order_status(client, symbol, sell_order_id)
                
                # 4시간 지나면 주문 취소한다.
                if conn.query(query_get_order_wait_time, (symbol,))[0][0]  > 10:# == 60*4:
                    raise TRADE_CANCLE('오래된 매도 주문 접수가 취소. 신규 매도 주문 접수를 대기')


                # 이전에 접수 되었던 예약 매도 주문이 취소되었거나 유효기간이 지나면 다시 예약 매도 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    raise TRADE_CANCLE('매도 주문 접수가 취소. 신규 매도 주문 접수를 대기')


                # 매도 주문이 체결될 때까지 대기
                elif order_status == ORDER_STATUS_NEW:
                    wait_time = conn.query(query_get_order_wait_time, (symbol,))[0][0] + 1
                    conn.query(query_update_order_wait_time, (wait_time, symbol))

                    LOG.info(f'주문대기###{symbol}###{wait_time}분')
                    

                # 매도 주문이 체결된 상태이며, 다시 매수 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    LOG.info(f'{symbol}#매도 주문 체결이 완료')

                    conn.query(query_update_status, ('BUY_ORDER_MONITOR', symbol))
                    conn.query(query_update_order_id, (None, None, symbol))
                    conn.query(query_update_order_wait_time, (0, symbol))


            except TRADE_CANCLE as e:
                cancle_order(client, symbol, sell_order_id)
                conn.query(query_update_status, ('SELL_ORDER_MONITOR', symbol))
                conn.query(query_update_order_id, (None, None, symbol))                
                conn.query(query_update_order_wait_time, (0, symbol))

                LOG.info(f'{symbol}###{e}')


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
        create_database()
        update_symbol_data(client)
   

    check_orderbook(client)
    check_has_coin(client)

    find_top_coin(client)
    find_rsi(client)


    scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Seoul')
    scheduler.add_job(find_top_coin, 'interval', hours=4, id="top_coin", args=(client,))
    scheduler.add_job(find_rsi, 'interval', minutes=1, id="find_rsi", args=(client,))
    scheduler.start()


#############################################################################


if __name__ == '__main__':

    print('Main Start')

    # 클라이언트 셋팅
    client = getClient()
    assert client

    #############################################################################

    #drop_table()
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

            LOG.info(f'트레이드 시작#{symbol}###{rsi}###{status}')
                        
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


        time.sleep(60)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################

