import datetime

A_MONTH = datetime.timedelta(days=30)
A_DAY = datetime.timedelta(days=1)


def is_pregnant_mother(case):
    return case.type == "cc_bihar_pregnancy"


def is_newborn_child(case):
    return case.type == "cc_bihar_newborn"


def get_date_attr(case, attr):
    value = getattr(case, attr, None)
    if not isinstance(value, datetime.datetime) and not isinstance(value, datetime.date):
        value = None
    return value


def get_edd(case):
    return get_date_attr(case, 'edd')


def get_add(case):
    return get_date_attr(case, 'add')


def relevant_predelivery_mother(case):
    return is_pregnant_mother(case) and get_edd(case)


def relevant_postdelivery_mother(case):
    return is_pregnant_mother(case) and get_add(case)