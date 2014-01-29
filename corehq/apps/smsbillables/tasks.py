import json
import logging
import urllib2
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from corehq.apps.accounting.models import Currency


update_logger = logging.getLogger("currency_update")
smsbillables_logger = logging.getLogger("smsbillables")


@periodic_task(run_every=crontab(minute=0, hour=9), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def update_exchange_rates(app_id=settings.OPEN_EXCHANGE_RATES_ID):
    try:
        update_logger.info("Updating exchange rates...")
        rates = json.load(urllib2.urlopen(
            'https://openexchangerates.org/api/latest.json?app_id=%s' % app_id))['rates']
        default_rate = float(rates[Currency.get_default().code])
        for code, rate in rates.items():
            currency, _ = Currency.objects.get_or_create(code=code)
            currency.rate_to_default = float(rate) / default_rate
            currency.save()
        update_logger.info("Exchange rates updated.")
    except Exception as e:
        smsbillables_logger.error(e.message)
