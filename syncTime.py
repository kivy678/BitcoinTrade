# -*- coding:utf-8 -*-

#############################################################################

import win32api
import time
from datetime import datetime

from binance import Client

from binance.exceptions import BinanceAPIException

#############################################################################

KEY ='키를 입력하세요.'
SECRET ='비밀키를 입력하세요.'

#############################################################################


if __name__ == '__main__':
    try:
        client = Client(KEY, SECRET, {"verify": True, "timeout": 20})
        server_time= client.get_server_time()

        print(server_time)

        gmtime = time.gmtime(int((server_time["serverTime"])/1000))
        win32api.SetSystemTime(gmtime[0],
                                gmtime[1],
                                0,
                                gmtime[2],
                                gmtime[3],
                                gmtime[4],
                                gmtime[5],
                                0)

        client.close_connection()

    except BinanceAPIException as e:
        print(e)
        exit()
