import datetime

from django.conf import settings

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from dimagi.utils.chunked import chunked
from dimagi.utils.dates import DateSpan

from corehq.apps.celery import periodic_task, task
from corehq.apps.data_analytics.gir_generator import GIRTableGenerator
from corehq.apps.data_analytics.malt_generator import generate_malt
from corehq.apps.data_analytics.util import (
    last_month_datespan,
    last_month_dict,
)
from corehq.apps.domain.models import Domain
from corehq.util.log import send_HTML_email
from corehq.util.soft_assert import soft_assert

logger = get_task_logger(__name__)


@periodic_task(queue=settings.CELERY_PERIODIC_QUEUE, run_every=crontab(hour=1, minute=0, day_of_month='2'),
               acks_late=True, ignore_result=True)
def build_last_month_MALT():
    last_month = last_month_dict()
    domains = Domain.get_all_names()
    for chunk in chunked(domains, 1000):
        update_malt.delay(last_month, chunk)


@periodic_task(queue=settings.CELERY_PERIODIC_QUEUE, run_every=crontab(hour=2, minute=0, day_of_week='*'),
               ignore_result=True)
def update_current_MALT():
    today = datetime.date.today()
    this_month_dict = {'month': today.month, 'year': today.year}
    domains = Domain.get_all_names()
    for chunk in chunked(domains, 1000):
        update_malt.delay(this_month_dict, chunk)


@periodic_task(queue=settings.CELERY_PERIODIC_QUEUE, run_every=crontab(hour=1, minute=0, day_of_month='3'),
               acks_late=True, ignore_result=True)
def build_last_month_GIR():
    last_month = last_month_datespan()
    try:
        generator = GIRTableGenerator([last_month])
        generator.build_table()
    except Exception as e:
        soft_assert(to=[settings.DATA_EMAIL], send_to_ops=False)(False, "Error in his month's GIR generation")
        # pass it so it gets logged in celery as an error as well
        raise e

    message = 'Global impact report generation for month {} is now ready. To download go to' \
              ' http://www.commcarehq.org/hq/admin/download_gir/'.format(
                  last_month
              )
    send_HTML_email(
        'GIR data is ready',
        settings.DATA_EMAIL,
        message,
        text_content=message
    )


@task(queue='malt_generation_queue')
def update_malt(month_dict, domains):
    month = DateSpan.from_month(month_dict['month'], month_dict['year'])
    generate_malt([month], domains=domains)
