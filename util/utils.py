# -*- coding:utf-8 -*-

#############################################################################

from datetime import datetime, timedelta

import pytz

#############################################################################


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


#https://semalt.tools/ko/timestamp-converter?time=1693146048
def utc_to_kst(t, col_data):

    # 바이낸스는 밀리세컨드를 쓴다
    unix_timestamp = t / 1000
    utc_time = datetime.utcfromtimestamp(unix_timestamp)
    korea_timezone = pytz.timezone('Asia/Seoul')
    korea_time = utc_time.replace(tzinfo=pytz.utc).astimezone(korea_timezone)

    return korea_time.strftime("%Y%m%dT%H%M%S")


def kst_to_utc(t):
    # 바이낸스는 밀리세컨드를 쓴다
    korea_timezone = pytz.timezone('Asia/Seoul')
    parsed_time = korea_timezone.localize(datetime.strptime(t, '%Y%m%dT%H%M%S'))

    # Unix 시간으로 변환
    unix_timestamp = (parsed_time - datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds() * 1000

    return int(unix_timestamp)



def get_today_midnight():
    # 현재 날짜와 시간 가져오기
    now = datetime.now()

    # 오늘 자정 구하기
    today_midnight = datetime(now.year, now.month, now.day, 0, 0, 0)

    # 원하는 형식으로 변환
    return today_midnight.strftime("%Y%m%dT%H%M%S")

