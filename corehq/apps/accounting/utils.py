import calendar
import datetime
import json
from django.utils.encoding import force_unicode
from django.utils.functional import Promise
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


def fmt_feature_rate_dict(feature, feature_rate=None):
    """
    This will be turned into a JSON representation of this Feature and its FeatureRate
    """
    if feature_rate is None:
        feature_rate = feature.get_rate()
    return {
        'name': feature.name,
        'feature_type': feature.feature_type,
        'feature_id': feature.id,
        'rate_id': feature_rate.id,
        'monthly_fee': feature_rate.monthly_fee.__str__(),
        'monthly_limit': feature_rate.monthly_limit,
        'per_excess_fee': feature_rate.per_excess_fee.__str__(),
    }


class LazyEncoder(json.JSONEncoder):
    """Taken from https://github.com/tomchristie/django-rest-framework/issues/87
    This makes sure that ugettext_lazy refrences in a dict are properly evaluated
    """
    def default(self, obj):
        if isinstance(obj, Promise):
            return force_unicode(obj)
        return super(LazyEncoder, self).default(obj)
