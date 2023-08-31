# -*- coding:utf-8 -*-

#############################################################################

from db import SQLite
from datetime import datetime, timedelta

#############################################################################

DB_CONFIG = {'database': r'var/database.db'}

TIME_FORMAT = '%Y%m%dT%H%M%S'

#############################################################################


def get_today():
    today = datetime.now()
    return today.strftime(TIME_FORMAT)


def str_to_date(t):
    return datetime.strptime(t, TIME_FORMAT)


def is_passed_time(t1, f, num):
    if f == 'hours':
        if  str_to_date(t1) < datetime.now() - timedelta(hours=num):
            return True     # 시간 후
        else:
            return False    # 시간 전

    elif f == 'minutes':
        if  str_to_date(t1) < datetime.now() - timedelta(minutes=num):
            return True     # 분 후
        else:
            return False    # 분 전


def time_check(column, time_type, time_number):
    conn = SQLite(DB_CONFIG)
    t = conn.query(f'SELECT {column} FROM trade;')[0][0]
    conn.close()

    if t:
        return False if is_passed_time(t, time_type, time_number) is True else True

    else:
        return False

