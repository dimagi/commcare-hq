from celery.schedules import crontab
from celery.task import task, periodic_task
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.alerts.ongoing_non_reporting import OnGoingNonReporting
from custom.ewsghana.alerts.ongoing_stockouts import OnGoingStockouts, OnGoingStockoutsRMS
from custom.ewsghana.alerts.urgent_alerts import UrgentNonReporting, UrgentStockoutAlert
from custom.ewsghana.api import EWSApi, EmailSettingsSync

from corehq.apps.commtrack.models import StockState, Product

from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.balance import BalanceMigration
from custom.ewsghana.extensions import ews_location_extension, ews_smsuser_extension, ews_webuser_extension, \
    ews_product_extension
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.reminders.first_soh_reminder import FirstSOHReminder
from custom.ewsghana.reminders.rrirv_reminder import RRIRVReminder
from custom.ewsghana.reminders.second_soh_reminder import SecondSOHReminder
from custom.ewsghana.reminders.stockout_reminder import StockoutReminder
from custom.ewsghana.reminders.third_soh_reminder import ThirdSOHReminder
from custom.ewsghana.reminders.visit_website_reminder import VisitWebsiteReminder
from custom.ewsghana.stock_data import EWSStockDataSynchronization
from custom.logistics.commtrack import bootstrap_domain as ews_bootstrap_domain, \
    bootstrap_domain
from custom.logistics.models import StockDataCheckpoint
from custom.logistics.tasks import stock_data_task
from dimagi.utils.couch.database import iter_docs


EXTENSIONS = {
    'product': ews_product_extension,
    'location_facility': ews_location_extension,
    'location_district': ews_location_extension,
    'location_region': ews_location_extension,
    'webuser': ews_webuser_extension,
    'smsuser': ews_smsuser_extension
}


# Region Greater Accra
EWS_FACILITIES = [304, 324, 330, 643, 327, 256, 637, 332, 326, 338, 340, 331, 347, 27, 975, 346, 477, 344, 339,
                  458, 748, 18, 379, 456, 644, 462, 459, 475, 638, 969, 480, 464, 960, 529, 255, 16, 31, 639, 640,
                  11, 15, 25, 645, 95, 13, 970, 952, 470, 971, 474, 962, 479, 953, 457, 476, 481, 501, 500, 499,
                  503, 502, 498, 496, 497, 10, 333, 963, 335, 972, 914, 527, 26, 531, 469, 530, 523, 19, 915, 524,
                  528, 325, 20, 460, 468, 916, 646, 519, 345, 471, 633, 518, 642, 328, 343, 21, 467, 648, 334, 473,
                  6, 342, 28, 478, 472, 955, 964, 636, 258, 918, 466, 337, 956, 809, 965, 24, 974, 957, 954, 22,
                  29, 958, 967, 917, 951, 515, 8, 959, 968, 649, 966, 341, 336, 647, 973, 5, 517, 522, 465, 635,
                  526, 4, 30, 1, 14, 23, 521, 532, 516, 461, 520, 525, 961, 641, 257, 348]


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


@task(queue='logistics_background_queue', ignore_result=True, acks_late=True)
def balance_migration_task(domain, date):
    endpoint = GhanaEndpoint.from_config(EWSGhanaConfig.for_domain(domain))
    BalanceMigration(domain, endpoint).balance_migration(date)
