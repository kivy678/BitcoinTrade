# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import pprint
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

    for symbol in client.get_all_tickers():
        symbol_name = symbol.get('symbol')

        if symbol_name.endswith('USDT') and                                     \
            client.get_symbol_info(symbol_name).get('status') == 'TRADING':

            print(symbol_name, get_min_size(symbol_name))


        time.sleep(1)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
