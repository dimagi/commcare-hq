from celery.schedules import crontab
from celery.task import task, periodic_task
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.alerts.ongoing_non_reporting import OnGoingNonReporting
from custom.ewsghana.alerts.ongoing_stockouts import OnGoingStockouts, OnGoingStockoutsRMS
from custom.ewsghana.alerts.urgent_alerts import UrgentNonReporting, UrgentStockoutAlert
from custom.ewsghana.api import EmailSettingsSync

from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.reminders.first_soh_reminder import FirstSOHReminder
from custom.ewsghana.reminders.rrirv_reminder import RRIRVReminder
from custom.ewsghana.reminders.second_soh_reminder import SecondSOHReminder
from custom.ewsghana.reminders.stockout_reminder import StockoutReminder
from custom.ewsghana.reminders.third_soh_reminder import ThirdSOHReminder
from custom.ewsghana.reminders.visit_website_reminder import VisitWebsiteReminder
from custom.logistics.utils import iterate_over_api_objects, get_username_for_user
from dimagi.utils.couch.database import iter_docs


# Alert when facilities have not been reported continuously for 3 weeks
@periodic_task(run_every=crontab(hour=10, minute=00),
               queue='logistics_reminder_queue')
def on_going_non_reporting():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        OnGoingNonReporting(domain).send()


# Ongoing STOCKOUTS at SDP and RMS
@periodic_task(run_every=crontab(hour=10, minute=25),
               queue='logistics_reminder_queue')
def on_going_stockout():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        OnGoingStockouts(domain).send()
        OnGoingStockoutsRMS(domain).send()


# Urgent Non-Reporting
# First monday of month
@periodic_task(run_every=crontab(day_of_week=1, day_of_month="1-7", hour=8, minute=20),
               queue='logistics_reminder_queue')
def urgent_non_reporting():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        UrgentNonReporting(domain).send()


# Urgent Stockout
# First monday of month
@periodic_task(run_every=crontab(day_of_week=1, day_of_month="1-7", hour=8, minute=20),
               queue='logistics_reminder_queue')
def urgent_stockout():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        UrgentStockoutAlert(domain).send()


# Thursday 13:54
@periodic_task(run_every=crontab(day_of_week=4, hour=13, minute=58),
               queue='logistics_reminder_queue')
def first_soh_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        FirstSOHReminder(domain).send()


# Monday 13:57
@periodic_task(run_every=crontab(day_of_week=1, hour=13, minute=57),
               queue='logistics_reminder_queue')
def second_soh_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        SecondSOHReminder(domain).send()


# Wednesday 13:54
@periodic_task(run_every=crontab(day_of_week=3, hour=13, minute=54),
               queue='logistics_reminder_queue')
def third_soh_to_super():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        ThirdSOHReminder(domain).send()


# Wednesday 14:06
@periodic_task(run_every=crontab(day_of_week=3, hour=14, minute=6),
               queue='logistics_reminder_queue')
def stockout_notification_to_web_supers():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        StockoutReminder(domain).send()


@periodic_task(run_every=crontab(day_of_month="28", hour=14, minute=15),
               queue='logistics_reminder_queue')
def reminder_to_submit_rrirv():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        RRIRVReminder(domain).send()


@periodic_task(run_every=crontab(month_of_year='1,4,7,10', day_of_month=4, hour=10, minute=3),
               queue='logistics_reminder_queue')
def reminder_to_visit_website():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        VisitWebsiteReminder(domain).send()


@task(queue='background_queue', ignore_result=True)
def migrate_email_settings(domain):
    config = EWSGhanaConfig.for_domain(domain)
    endpoint = GhanaEndpoint.from_config(config)
    migrate_email = EmailSettingsSync(domain)

    for report in endpoint.get_daily_reports()[1]:
        migrate_email.daily_report_sync(report)

    for report in endpoint.get_weekly_reports()[1]:
        migrate_email.weekly_report_sync(report)

    for report in endpoint.get_monthly_reports()[1]:
        migrate_email.monthly_report_sync(report)


@task(queue='logistics_background_queue', ignore_result=True)
def migrate_needs_reminders_field_task(domain):
    config = EWSGhanaConfig.for_domain(domain)
    endpoint = GhanaEndpoint.from_config(config)

    for sms_user in iterate_over_api_objects(endpoint.get_smsusers, filters={'needs_reminders': False}):
        username = get_username_for_user(domain, sms_user)[0]
        couch_user = CommCareUser.get_by_username(username)

        if couch_user and couch_user.user_data.get('needs_reminders') != 'False':
            couch_user['user_data']['needs_reminders'] = "False"
            couch_user.save()

    ids = CommCareUser.ids_by_domain(domain)

    to_save = []
    for user in iter_docs(CommCareUser.get_db(), ids):
        if 'needs_reminders' not in user['user_data']:
            user['user_data']['needs_reminders'] = "True"
            to_save.append(user)

            if len(to_save) > 500:
                CommCareUser.get_db().bulk_save(to_save)
                to_save = []

    if to_save:
        CommCareUser.get_db().bulk_save(to_save)
