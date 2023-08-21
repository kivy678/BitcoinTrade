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

exclude_coin   = ['UP', 'DOWN', 'BEAR', 'BULL', 'USDC', 'BUSD', 'TUSD', 'DAI', 'GUSD', 'EUR'] # 레버리지 및 스테이블 코인

CHOICE_COIN = 'HIGHT'
MONITORING_COIN = 5

lock_load = threading.Lock()
lock_save = threading.Lock()

#############################################################################

def time_check(j, k, f):
    t = j.get(k)
    
    if t:
        return False if is_passed_time(t, f) is True else True

    else:
        return False

def load_file(path):
    with lock_load:
        with open(path, 'r', encoding='utf-8-sig') as fr:
            return json.load(fr)


def save_file(path, data):
    with lock_save:
        with open(path, 'w', encoding='utf-8') as fw:
            json.dump(data, fw, indent=4, separators=(',', ': '))


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
                                        'bought':           False,
                                        'tick_size':        tick_size,
                                        'step_size':        step_size,
                                        'min_lot':          min_lot,
                                        'min_noti':         min_noti,
                                        'luctuation_rate':  None,
                                        'trading':          False,
                                        'rsi': 50}})

            trade_system['init_time'] = get_today()
            trade_system['sum_noti']  = 0

    else:
        # 이미 저장되어 있으면 파일 로드
        LOG.info('load order_book')
        order_book      = load_file(SYMBOL_PATH)
        trade_system    = load_file(TRADING_PATH)
        
        for symbol in order_book:
            order_book[symbol]['buy_orderId']    = None
            order_book[symbol]['sell_orderId']   = None
            order_book[symbol]['bought']         = False

        trade_system['sum_noti']  = 0


    # 오더북 체크
    for info in get_open_orders(client):
        if info.get('side') == 'BUY' and info.get('status') == ORDER_STATUS_NEW:
            symbol      = info.get('symbol')
            rsi         = get_rsi(info.get('symbol'))
            orderId     = info.get('orderId')

            # RSI가 30이상이면 buy 주문 유지 할필요 없기 때문에 취소한다.
            if rsi > 30:
                LOG.info(f'{symbol}:RSI 오버로 주문을 취소합니다.')
                cancle_order(client, symbol, orderId)
            else:
                LOG.info(f'{symbol}:BUY 주문번호 저장')
                order_book[info.get('symbol')]['buy_orderId'] = info.get('orderId')


        elif info.get('side') == 'SELL' and info.get('status') == ORDER_STATUS_NEW:
            symbol      = info.get('symbol')
            rsi         = get_rsi(info.get('symbol'))
            orderId     = info.get('orderId')

            # RSI가 30이상이면 buy 주문 유지 할필요 없기 때문에 취소한다.
            if rsi < 10:
                LOG.info(f'{symbol}:RSI 오버로 주문을 취소합니다.')
                cancle_order(client, symbol, orderId)
            else:
                LOG.info(f'{symbol}:SELL 주문번호 저장')
                order_book[info.get('symbol')]['sell_orderId'] = info.get('orderId')
                order_book[symbol]['bought']         = True


    # 현재 가지고 있는 코인이 매매 최소 수량보다 크다면 판매가 가능하므로 SELL 로직으로 넘긴다.
    for info in client.get_account().get('balances'):
        money = float(info.get('free'))
        asset = info.get('asset')

        if (money > 0) and (asset != 'USDT' and asset != 'BNB'):
            asset += 'USDT'
            print(asset, money, get_require_min_qty(client, asset, order_book))
            #if money >= get_require_min_qty(client, asset, order_book):
            LOG.info(f'{asset}#구매한 코인#{money}')
            order_book[asset]['bought'] = True


    # 파일로 저장
    LOG.info('save order_book')
    save_file(SYMBOL_PATH, order_book)
    save_file(TRADING_PATH, trade_system)

    return order_book, trade_system


def get_fluctuation_rate(client, symbol):
    klines = get_historical_klines_1hour(client, symbol)
    return (pd.DataFrame(klines)[4].astype(float).pct_change() + 1).prod() - 1
    


# 인기 있는 상위 코인 30개만 모니터링
def find_top_coin(client, order_book, trade_system):
    
    # 1시간마다 모든 코인의 등락율 계산
    if time_check(trade_system, 'luctuation_rate_time', 'hours') is False:
        LOG.info('코인 등락율 계산 중...')
        for symbol in tqdm(order_book):
            luctuation_rate = get_fluctuation_rate(client, symbol)
            order_book[symbol]['luctuation_rate'] = np.round(luctuation_rate*100, 2)


        trade_system['luctuation_rate_time'] = get_today()


        # 트레이딩 정보 초기화
        for symbol in order_book:
            order_book[symbol]['rsi'] = 50
            order_book[symbol]['trading'] = False
               
        
        # 상위 코인 30개 가져오기
        luctuation_rate, symbols = list(), list()
        for symbol in order_book:
            symbols.append(symbol)
            luctuation_rate.append(order_book.get(symbol).get('luctuation_rate'))

        top_coin = pd.DataFrame(luctuation_rate, index=symbols, columns=['rate'])


        if CHOICE_COIN == 'HIGHT':
            for symbol, rate in top_coin.rate.nlargest(MONITORING_COIN).iteritems():
                order_book[symbol]['trading'] = True

        elif CHOICE_COIN == 'LOW':
            for symbol, rate in top_coin.rate.nsmallest(MONITORING_COIN).iteritems():
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


def loop_find_coin(client, order_book, trade_system):

    while True:
        # 모니터링 할 코인 찾기
        find_top_coin(client, order_book, trade_system)

        # RSI 전부 계산
        find_rsi(client, order_book, trade_system)


        sum_noti = 0
        for symbol in order_book:
            if order_book[symbol].get('trading'):
                sum_noti += order_book[symbol].get('min_noti')


        trade_system['sum_noti'] = sum_noti

        save_file(SYMBOL_PATH, order_book)
        save_file(TRADING_PATH, trade_system)


        time.sleep(60*15)



def buy_logic(client, symbol, order_book, buy_order_id=None):
    print(f'{symbol}#start buy logic')
    #############################################################################
    # 매수 로직
    #############################################################################
    buy_log_cnt = 0

    while True:
        try:
            # 매수된 코인이 없기 때문에 매수 주문서 접수 대기
            if buy_order_id is None:
                buy_order_id = order_buy(client, symbol, order_book)
                        

            # 신규 매수 주문 접수가 완료 되었고 매수 체결이 이루어 졌는지 확인 해야한다.
            elif buy_order_id is not None:
                order_status = get_order_status(client, symbol, buy_order_id)
                
                # 매수 주문이 체결될 때까지 대기
                if order_status == ORDER_STATUS_NEW:
                    time.sleep(1)
                    

                # 이전에 접수 되었던 예약 매수 주문이 취소되었거나 유효기간이 지나면 다시 예약 매수 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    LOG.info(f'{symbol}#매수 주문 접수가 취소. 신규 매수 주문 접수를 대기')
                    buy_order_id = order_book[symbol]['buy_orderId']    = None
                    

                # 주문이 체결된 상태이며, 매도 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    LOG.info(f'{symbol}#매수 주문 체결 완료')
                    buy_order_id = order_book[symbol]['buy_orderId']    = None
                    order_book[symbol]['bought']                        = True
                    save_file(SYMBOL_PATH, order_book)
                    
                    return


        except Exception as e:
            LOG.info(f'{symbol}#{e}')

        if buy_log_cnt == 180:
            cancle_order(client, symbol, buy_order_id)
            buy_order_id = order_book[symbol]['buy_orderId']    = None
            save_file(SYMBOL_PATH, order_book)
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
   

            # 신규 매도 주문 접수가 완료 되었고 매도 체결이 이루어 졌는지 확인 해야한다.
            elif sell_order_id is not None:
                order_status = get_order_status(client, symbol, sell_order_id)
                
                # 매도 주문이 체결될 때까지 대기
                if order_status == ORDER_STATUS_NEW:
                    time.sleep(1)
                    

                # 이전에 접수 되었던 예약 매도 주문이 취소되었거나 유효기간이 지나면 다시 예약 매도 주문이 접수될 때까지 대기
                elif order_status in (ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED):
                    LOG.info(f'{symbol}#매도 주문 접수가 취소. 신규 매도 주문 접수를 대기')
                    sell_order_id = order_book[symbol]['sell_orderId'] = None
                    

                # 매도 주문이 체결된 상태이며, 다시 매수 로직으로 넘어간다.
                elif order_status == ORDER_STATUS_FILLED:
                    LOG.info(f'{symbol}#매도 주문 체결이 완료')
                    sell_order_id = order_book[symbol]['sell_orderId']  = None
                    order_book[symbol]['bought']                        = False
                    save_file(SYMBOL_PATH, order_book)

                    return

        except Exception as e:
           LOG.info(f'{symbol}#{e}')

        if sell_log_cnt == 180:
            cancle_order(client, symbol, sell_order_id)
            sell_order_id = order_book[symbol]['sell_orderId']  = None
            save_file(SYMBOL_PATH, order_book)
            LOG.info(f'{symbol}#15분째 매도 주문이 체결이 안되서 주문을 취소')
            
            return

        else:
            sell_log_cnt += 1
            time.sleep(5)


if __name__ == '__main__':

    print('Main Start')

    # 클라이언트 셋팅
    client = getClient()
    assert client

    order_book, trade_system = init_trade(client)

    # 등락율 계산과 RSI 계산
    find_coin_thread = Thread(target=loop_find_coin, args=(client, order_book, trade_system,))
    find_coin_thread.daemon = True
    find_coin_thread.start()


    # 트레이딩인 RSI을 가져와서 조건에 맞는 코인은 매수 로직 태우기
    while True:
        # 오더북 전체 루프 시작
        order_book      = load_file(SYMBOL_PATH)
        trade_system    = load_file(TRADING_PATH)

        for symbol in order_book:
            if order_book[symbol].get('trading'):
                rsi             = order_book[symbol].get('rsi')
                buy_orderId     = order_book[symbol].get('buy_orderId')
                sell_orderId    = order_book[symbol].get('sell_orderId')
                bought          = order_book[symbol].get('bought')
                min_noti        = order_book[symbol].get('min_noti')
                
                LOG.info(f'트레이드 시작#{symbol}')


                # 코인을 구입했다면 sell_logic 을 태운다.
                if bought is True  and rsi >= 70 and get_asset_balance(client) < min_noti:
                    sell_thread = Thread(target=sell_logic, args=(client, symbol, order_book, sell_orderId,))
                    sell_thread.daemon = True
                    sell_thread.start()

                elif bought is False and rsi <= 30 and get_asset_balance(client) > min_noti:
                    buy_thread = Thread(target=buy_logic, args=(client, symbol, order_book, buy_orderId,))
                    buy_thread.daemon = True
                    buy_thread.start()

                time.sleep(1)

        # 60초정도 루프
        LOG.info(f'60초 대기')        
        time.sleep(60)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
