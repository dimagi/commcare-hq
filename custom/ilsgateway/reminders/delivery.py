from functools import partial
from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.reminders import REMINDER_DELIVERY_FACILITY, REMINDER_DELIVERY_DISTRICT, update_statuses
from custom.ilsgateway.utils import send_for_day, get_current_group, get_groups
import settings


def send_delivery_reminder(domain, date, loc_type='FACILITY'):
    if loc_type == 'FACILITY':
        status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
        sms_text = REMINDER_DELIVERY_FACILITY
    elif loc_type == 'DISTRICT':
        status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT
        sms_text = REMINDER_DELIVERY_DISTRICT
    else:
        return
    current_group = get_current_group()
    sp_ids = set()
    for user in CommTrackUser.by_domain(domain):
        if user.is_active and user.location and user.location.location_type == loc_type:
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and current_group in get_groups(sp.location.metadata.get('groups', None)) and not \
                    SupplyPointStatus.objects.filter(supply_point=sp._id,
                                                     status_type=status_type,
                                                     status_date__gte=date).exists():
                if user.get_verified_number():
                    send_sms_to_verified_number(user.get_verified_number(), sms_text)
                    sp_ids.add(sp._id)
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