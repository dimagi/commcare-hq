import calendar
import datetime
from corehq import Domain
from dimagi.utils.dates import add_months


EXCHANGE_RATE_DECIMAL_PLACES = 9


def get_previous_month_date_range(reference_date=None):
    reference_date = reference_date or datetime.date.today()

    last_month_year, last_month = add_months(reference_date.year, reference_date.month, -1)
    _, last_day = calendar.monthrange(last_month_year, last_month)
    date_start = datetime.date(last_month_year, last_month, 1)
    date_end = datetime.date(last_month_year, last_month, last_day)

    return date_start, date_end


def months_from_date(reference_date, months_from_date):
    year, month = add_months(reference_date.year, reference_date.month, months_from_date)
    return datetime.date(year, month, 1)


def assure_domain_instance(domain):
    if not isinstance(domain, Domain):
        domain = Domain.get_by_name(domain)
    return domain
