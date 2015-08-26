from celery.schedules import crontab

from celery.task import periodic_task

from custom.ewsghana.models import EWSGhanaConfig

from custom.ewsghana.reminders.first_soh_reminder import FirstSOHReminder
from custom.ewsghana.reminders.rrirv_reminder import RRIRVReminder
from custom.ewsghana.reminders.second_soh_reminder import SecondSOHReminder
from custom.ewsghana.reminders.stockout_reminder import StockoutReminder
from custom.ewsghana.reminders.third_soh_reminder import ThirdSOHReminder
from custom.ewsghana.reminders.visit_website_reminder import VisitWebsiteReminder
import settings


@periodic_task(run_every=crontab(day_of_week=3, hour=13, minute=58),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_soh_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        FirstSOHReminder(domain).send()


@periodic_task(run_every=crontab(day_of_week=0, hour=13, minute=57),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_soh_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        SecondSOHReminder(domain).send()


@periodic_task(run_every=crontab(day_of_week=2, hour=13, minute=54),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_soh_to_super():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        ThirdSOHReminder(domain).send()


@periodic_task(run_every=crontab(day_of_month="2", hour=14, minute=6),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def stockout_notification_to_web_supers():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        StockoutReminder(domain).send()


@periodic_task(run_every=crontab(day_of_month="28", hour=14, minute=15),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_submit_rrirv():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        RRIRVReminder(domain).send()


@periodic_task(run_every=crontab(month_of_year='1,4,7,10', day_of_month=4, hour=10, minute=3),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_visit_website():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        VisitWebsiteReminder(domain).send()
