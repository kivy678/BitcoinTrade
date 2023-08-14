# -*- coding:utf-8 -*-

#############################################################################

from datetime import datetime

#############################################################################


def get_today():
    today = datetime.now()
    date_string = today.strftime('%Y-%m-%d')

    return date_string

