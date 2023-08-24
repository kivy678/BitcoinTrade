# -*- coding:utf-8 -*-

#############################################################################

from datetime import datetime, timedelta

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
			return True 	# 시간 후
		else:
			return False 	# 시간 전

	elif f == 'minutes':
		if  str_to_date(t1) < datetime.now() - timedelta(minutes=num):
			return True 	# 분 후
		else:
			return False 	# 분 전

