import datetime


def days_visit_overdue(form):
    val = form.xpath('form/case/update/days_visit_overdue')
    if val not in (None, ''):
        return int(val)
    else:
        return val


def date_modified(form):
    val = form.xpath('form/case/@date_modified')
    if isinstance(val, datetime.datetime):
        return val.date()
    else:
        return val


def date_next_bp(form):
    return form.xpath('form/case/update/date_next_bp') or None
