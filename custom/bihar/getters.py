from __future__ import absolute_import
import datetime


def days_visit_overdue(form):
    val = form.get_data('form/case/update/days_visit_overdue')
    if val not in (None, ''):
        return int(val)
    else:
        return val


def date_modified(form, force_to_date=True, force_to_datetime=False):
    val = form.get_data('form/case/@date_modified')
    if force_to_date and isinstance(val, datetime.datetime):
        return val.date()
    elif force_to_datetime and isinstance(val, datetime.date):
        return datetime.datetime.combine(val, datetime.time())
    else:
        return val


def date_next_bp(form):
    return form.get_data('form/case/update/date_next_bp') or None


def date_next_pnc(form):
    return form.get_data('form/case/update/date_next_pnc') or None


def date_next_eb(form):
    return form.get_data('form/case/update/date_next_eb') or None


def date_next_cf(form):
    return form.get_data('form/case/update/date_next_cf') or None
