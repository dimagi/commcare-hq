from __future__ import absolute_import
from __future__ import unicode_literals
from celery.schedules import crontab
from celery.task import periodic_task
from celery.utils.log import get_task_logger
import datetime

from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from corehq.apps.data_analytics.gir_generator import GIRTableGenerator
from dimagi.utils.dates import DateSpan
from corehq.util.log import send_HTML_email
from django.conf import settings

logger = get_task_logger(__name__)


@periodic_task(queue='background_queue', run_every=crontab(hour=1, minute=0, day_of_month='2'),
               acks_late=True, ignore_result=True)
def build_last_month_MALT():
    def _last_month_datespan():
        today = datetime.date.today()
        first_of_this_month = datetime.date(day=1, month=today.month, year=today.year)
        last_month = first_of_this_month - datetime.timedelta(days=1)
        return DateSpan.from_month(last_month.month, last_month.year)

    last_month = _last_month_datespan()
    generator = MALTTableGenerator([last_month])
    generator.build_table()

    message = 'MALT generation for month {} is now ready. To download go to'\
              ' http://www.commcarehq.org/hq/admin/download_malt/'.format(
                  last_month
              )
    send_HTML_email(
        'MALT is ready',
        settings.DATA_EMAIL,
        message,
        text_content=message
    )


@periodic_task(queue='background_queue', run_every=crontab(hour=2, minute=0, day_of_week='*'),
               ignore_result=True)
def update_current_MALT():
    today = datetime.date.today()
    this_month = DateSpan.from_month(today.month, today.year)
    MALTTableGenerator([this_month]).build_table()


@periodic_task(queue='background_queue', run_every=crontab(hour=1, minute=0, day_of_month='3'),
               acks_late=True, ignore_result=True)
def build_last_month_GIR():
    def _last_month_datespan():
        today = datetime.date.today()
        first_of_this_month = datetime.date(day=1, month=today.month, year=today.year)
        last_month = first_of_this_month - datetime.timedelta(days=1)
        return DateSpan.from_month(last_month.month, last_month.year)

    last_month = _last_month_datespan()
    generator = GIRTableGenerator([last_month])
    generator.build_table()

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

