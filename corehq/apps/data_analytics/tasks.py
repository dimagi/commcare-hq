from celery.schedules import crontab
from celery.task import periodic_task
from celery.utils.log import get_task_logger
import datetime

from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from dimagi.utils.dates import DateSpan
from dimagi.utils.django.email import send_HTML_email
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
