import datetime
import time


def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()


def unix_time_millis(dt):
    return unix_time(dt) * 1000.0


def get_timestamp(date):
    return time.mktime(date.timetuple())


def get_timestamp_millis(date):
    return 1000 * get_timestamp(date)
