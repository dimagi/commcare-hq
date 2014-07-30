import datetime
from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms
from corehq.apps.users.models import CouchUser
from custom.ilsgateway.models import SupplyPointStatusValues, SupplyPointStatusTypes
from custom.ilsgateway.reminders import REMINDER_STOCKONHAND, update_status
from casexml.apps.stock.models import StockTransaction
from dimagi.utils.dates import get_business_day_of_month
import settings


def send_soh_reminder(domain, date):
    for user in CommTrackUser.by_domain(domain):
        if user.location and user.location.location_type == 'FACILITY':
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and not StockTransaction.objects.filter(case_id=sp._id, report__date__gte=date,
                                                          type='stockonhand').exists():
                couch_user = CouchUser.wrap(user.to_json())
                update_status(sp._id, SupplyPointStatusTypes.SOH_FACILITY,
                    SupplyPointStatusValues.REMINDER_SENT)
                send_sms(domain, user, couch_user.default_phone_number, REMINDER_STOCKONHAND)


def get_last_and_nth_business_day(date, n):
    last_month = datetime.datetime(date.year, date.month, 1) - datetime.timedelta(days=1)
    last_month_last_day = get_business_day_of_month(month=last_month.month, year=last_month.year, count=-1)
    nth_business_day = get_business_day_of_month(month=date.month, year=date.year, count=n)
    return last_month_last_day, nth_business_day


def send_for_all_domains(date):
    for domain in Domain.get_all():
        #TODO Merge with ILSGateway integration?
        #ilsgateway_config = ILSGatewayConfig.for_domain(domain.name)
        #if ilsgateway_config and ilsgateway_config.enabled:
        send_soh_reminder(domain.name, date)


@periodic_task(run_every=crontab(day_of_month="26-31", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_soh_task():
    now = datetime.datetime.utcnow()
    last_buisness_day = get_business_day_of_month(month=now.month, year=now.year, count=-1)
    if now.day == last_buisness_day.day:
        send_for_all_domains(last_buisness_day)


@periodic_task(run_every=crontab(day_of_month="1-3", hour=9, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_soh_task():
    now = datetime.datetime.utcnow()
    last_month_last_day, first_business_day = get_last_and_nth_business_day(now, 1)
    if now.day == first_business_day.day:
        send_for_all_domains(last_month_last_day)


@periodic_task(run_every=crontab(day_of_month="5-7", hour=8, minute=15), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_soh_task():
    now = datetime.datetime.utcnow()
    last_month_last_day, fifth_business_day = get_last_and_nth_business_day(now, 5)
    if now.day == fifth_business_day.day:
        send_for_all_domains(last_month_last_day)