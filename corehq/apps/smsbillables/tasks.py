import json
import urllib2
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings
from celery.utils.log import get_task_logger

from corehq.apps.accounting.models import Currency


logger = get_task_logger("accounting")


@periodic_task(run_every=crontab(minute=0, hour=0), queue='background_queue')
def update_exchange_rates(app_id=settings.OPEN_EXCHANGE_RATES_ID):
    try:
        logger.info("Updating exchange rates...")
        rates = json.load(urllib2.urlopen(
            'https://openexchangerates.org/api/latest.json?app_id=%s' % app_id))['rates']
        default_rate = float(rates[Currency.get_default().code])
        for code, rate in rates.items():
            currency, _ = Currency.objects.get_or_create(code=code)
            currency.rate_to_default = float(rate) / default_rate
            currency.save()
            logger.info("Exchange rate for %(code)s updated %(rate)f." % {
                'code': currency.code,
                'rate': currency.rate_to_default,
            })
    except Exception as e:
        logger.error(e.message)
