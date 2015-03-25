from functools import partial

from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues, \
    DeliveryGroups
from custom.ilsgateway.tanzania.reminders import REMINDER_DELIVERY_FACILITY, REMINDER_DELIVERY_DISTRICT, \
    update_statuses
from custom.ilsgateway.utils import send_for_day, send_translated_message
import settings


def send_delivery_reminder(domain, date, loc_type='FACILITY', test_list=None):
    if loc_type == 'FACILITY':
        status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
        sms_text = REMINDER_DELIVERY_FACILITY
    elif loc_type == 'DISTRICT':
        status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT
        sms_text = REMINDER_DELIVERY_DISTRICT
    else:
        return
    current_group = DeliveryGroups().current_delivering_group(date.month)
    sp_ids = set()
    users = CommCareUser.by_domain(domain) if not test_list else test_list
    for user in users:
        location = user.location
        if user.is_active and location and location.location_type == loc_type:
            status_exists = SupplyPointStatus.objects.filter(
                supply_point=location._id,
                status_type=status_type,
                status_date__gte=date
            ).exists()
            groups = location.metadata.get('group', None)
            if groups and current_group in groups and not status_exists:
                send_translated_message(user, sms_text)
    update_statuses(sp_ids, status_type, SupplyPointStatusValues.REMINDER_SENT)


facility_partial = partial(send_for_day, cutoff=15, f=send_delivery_reminder)
district_partial = partial(send_for_day, cutoff=13, f=send_delivery_reminder, loc_type='DISTRICT')


@periodic_task(run_every=crontab(day_of_month="13-15", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_facility_delivery_task():
    facility_partial(15)


@periodic_task(run_every=crontab(day_of_month="20-22", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_facility_delivery_task():
    facility_partial(22)


@periodic_task(run_every=crontab(day_of_month="26-30", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_facility_delivery_task():
    facility_partial(30)


@periodic_task(run_every=crontab(day_of_month="11-13", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_district_delivery_task():
    district_partial(13)


@periodic_task(run_every=crontab(day_of_month="18-20", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_district_delivery_task():
    district_partial(20)


@periodic_task(run_every=crontab(day_of_month="26-28", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_district_delivery_task():
    district_partial(28)
