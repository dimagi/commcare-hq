from celery.schedules import crontab
from celery.task import periodic_task
from celery.utils.log import get_task_logger
import datetime

from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from dimagi.utils.dates import DateSpan


logger = get_task_logger(__name__)


@periodic_task(run_every=crontab(hour=1, minute=0, day_of_month='2'))
def build_las_month_MALT():
    def _last_month_datespan():
        today = datetime.date.today()
        first_of_this_month = datetime.date(day=1, month=today.month, year=today.year)
        last_month = first_of_this_month - datetime.timedelta(days=1)
        return DateSpan.from_month(last_month.month, last_month.year)

    generator = MALTTableGenerator([_last_month_datespan()])
    generator.build_table()
