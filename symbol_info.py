# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import pprint

from tqdm import tqdm
from util.bapi import *
from binance.helpers import round_step_size

#############################################################################


def get_min_size(symbol):
    for info in client.get_symbol_info(symbol).get('filters'):
        if info.get('filterType') == 'LOT_SIZE':
            minQty = info.get('minQty')

        elif info.get('filterType') == 'NOTIONAL':
            minNotional = info.get('minNotional')

    min_size = round_step_size(float(minNotional) /
                                float(client.get_avg_price(symbol=symbol).get('price')), minQty)

    return min_size


if __name__ == '__main__':

    print('Main Start')
     
    client = getClient()
    assert client


    min_size = get_min_size('BTCUSDT')
    print(min_size)


    info =  client.get_exchange_info()
    exclude_coin   = ['UP', 'DOWN', 'BEAR', 'BULL'] # 레버리지 코인

    for x in info.get('symbols'):
        symbol_name = x.get('symbol')

        # USDT 이고 레버리지 코인이 아니며, 트레이딩이 가능한 코인
        if symbol_name.endswith('USDT') and                                     \
            all(exclude not in symbol_name for exclude in exclude_coin) and     \
            x.get('status') == 'TRADING':

            print(symbol_name, get_min_size(symbol_name))

            time.sleep(2)



    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
