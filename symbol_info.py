# -*- coding:utf-8 -*-

#############################################################################

import warnings
warnings.filterwarnings("ignore")

import pprint
from util.bapi import *
from binance.helpers import round_step_size

#############################################################################


if __name__ == '__main__':

    print('Main Start')
     
    client = getClient()
    assert client

    for info in client.get_symbol_info('BTCUSDT').get('filters'):
        if info.get('filterType') == 'LOT_SIZE':
            minQty = info.get('minQty')

        elif info.get('filterType') == 'NOTIONAL':
            minNotional = info.get('minNotional')

    min_size = round_step_size(float(minNotional) /
                                float(client.get_avg_price(symbol='BTCUSDT').get('price')), minQty)
    print(min_size)


    #############################################################################

    closeClient(client)

    print('Main End')

    #############################################################################
