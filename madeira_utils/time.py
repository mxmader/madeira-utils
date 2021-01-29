from datetime import datetime


def get_timestamp():
    return round(datetime.utcnow().timestamp())


def get_timestamp_object():
    return datetime.utcnow()
