import datetime

from django.conf import settings

from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger

from dimagi.utils.dates import DateSpan

from corehq.apps.data_analytics.gir_generator import GIRTableGenerator
from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from corehq.apps.domain.models import Domain
from corehq.util.log import send_HTML_email
from corehq.util.soft_assert import soft_assert

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
    domains = Domain.get_all()
    grouped_malt_tasks = update_current_MALT_for_domains.chunks(
        zip(last_month, domains), 5000
    ).group()

    # this blocks until all subtasks are complete which is not recommended by celery
    # having multiple workers mitigates the risk of a deadlock between this main task and the child tasks
    grouped_malt_tasks().get(disable_sync_subtasks=False)
    send_MALT_complete_email(last_month)


@periodic_task(queue='background_queue', run_every=crontab(hour=2, minute=0, day_of_week='*'),
               ignore_result=True)
def update_current_MALT():
    today = datetime.date.today()
    this_month = DateSpan.from_month(today.month, today.year)
    domains = Domain.get_all()
    update_current_MALT_for_domains.chunks(zip(this_month, domains), 5000).apply_async()


@periodic_task(queue='background_queue', run_every=crontab(hour=1, minute=0, day_of_month='3'),
               acks_late=True, ignore_result=True)
def build_last_month_GIR():
    def _last_month_datespan():
        today = datetime.date.today()
        first_of_this_month = datetime.date(day=1, month=today.month, year=today.year)
        last_month = first_of_this_month - datetime.timedelta(days=1)
        return DateSpan.from_month(last_month.month, last_month.year)

    last_month = _last_month_datespan()
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


@task(queue='background_queue')
def update_current_MALT_for_domains(month, domains):
    MALTTableGenerator([month]).build_table(domains=domains)


@task(queue='background_queue')
def send_MALT_complete_email(month):
    message = 'MALT generation for month {} is now ready. To download go to'\
              ' http://www.commcarehq.org/hq/admin/download_malt/'.format(
                  month
              )
    send_HTML_email(
        'MALT is ready',
        settings.DATA_EMAIL,
        message,
        text_content=message
    )
