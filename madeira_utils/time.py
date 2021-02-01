from datetime import datetime


def get_days_since(reference_date):
    round((get_timestamp() - reference_date) / 86400)


def get_timestamp():
    return round(datetime.utcnow().timestamp())


def get_timestamp_object():
    return datetime.utcnow()


def get_year():
    return get_timestamp_object().year


def get_year_start(year):
    return datetime(int(year), 1, 1, 0, 0, 0)
