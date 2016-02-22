import json
import urllib2
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from corehq.apps.accounting.models import Currency
from corehq.apps.accounting.utils import log_accounting_error, log_accounting_info


@periodic_task(run_every=crontab(minute=0, hour=0), queue='background_queue')
def update_exchange_rates(app_id=settings.OPEN_EXCHANGE_RATES_API_ID):
    try:
        log_accounting_info("Updating exchange rates...")
        rates = json.load(urllib2.urlopen(
            'https://openexchangerates.org/api/latest.json?app_id=%s' % app_id))['rates']
        default_rate = float(rates[Currency.get_default().code])
        for code, rate in rates.items():
            currency, _ = Currency.objects.get_or_create(code=code)
            currency.rate_to_default = float(rate) / default_rate
            currency.save()
            log_accounting_info("Exchange rate for %(code)s updated %(rate)f." % {
                'code': currency.code,
                'rate': currency.rate_to_default,
            })
    except Exception as e:
        log_accounting_error(e.message)
