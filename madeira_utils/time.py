from datetime import datetime


def get_timestamp():
    return round(datetime.utcnow().timestamp())


def get_timestamp_object():
    return datetime.utcnow()


def get_year_start(year):
    return datetime(int(year), 1, 1, 0, 0, 0)
