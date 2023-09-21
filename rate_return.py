# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import pprint

from binance import Client
from binance.exceptions import BinanceAPIException

from env import *

from util.bapi import *
from util.Logger import LOG
from util.utils import *
import numpy as np

#############################################################################



def kst_to_utc(t):
    # 바이낸스는 밀리세컨드를 쓴다
    korea_timezone = pytz.timezone('Asia/Seoul')
    parsed_time = korea_timezone.localize(datetime.strptime(t, '%Y%m%dT%H%M%S'))

    # Unix 시간으로 변환
    unix_timestamp = (parsed_time - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000

    return int(unix_timestamp)



client = getClient()
assert client

#server_time_sync(client)


agg_trades = client.get_my_trades(symbol='BTCUSDT',
                                  startTime=kst_to_utc('20230922T000000'))


initial_values = list()
final_values = list()

for trade_info in agg_trades:
    t           = trade_info.get('time')
    qty         = float(trade_info.get('qty'))
    quoteQty    = float(trade_info.get('quoteQty'))
    price       = float(trade_info.get('price'))
    commission  = float(trade_info.get('commission'))
    buyer       = 'buy' if trade_info.get('isBuyer') else 'sell'     

    print(f'quoteQty:{quoteQty}###price:{price}###buyer:{buyer}')  


    if trade_info.get('isBuyer'):
        initial_values.append(quoteQty)
    else:
        final_values.append(quoteQty)

  
initial_values = sum(initial_values)
final_values = sum(final_values)


rate = ((final_values - initial_values) / initial_values)*100
print(f'수익률: {np.round(rate, 2)}')


closeClient(client)

print('Main End')

