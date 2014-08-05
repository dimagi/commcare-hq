from functools import partial
from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.reminders import REMINDER_R_AND_R_FACILITY, update_statuses, \
    REMINDER_R_AND_R_DISTRICT
from custom.ilsgateway.utils import get_current_group, send_for_day, get_groups
import settings


def send_ror_reminder(domain, date, loc_type='FACILITY'):
    if loc_type == 'FACILITY':
        status_type = SupplyPointStatusTypes.R_AND_R_FACILITY
        sms_text = REMINDER_R_AND_R_FACILITY
    elif loc_type == 'DISTRICT':
        status_type = SupplyPointStatusTypes.R_AND_R_DISTRICT
        sms_text = REMINDER_R_AND_R_DISTRICT
    else:
        return
    current_group = get_current_group()
    sp_ids = set()
    for user in CommTrackUser.by_domain(domain):
        if user.is_active and user.location and user.location.location_type == loc_type:
            sp = SupplyPointCase.get_by_location(user.location)
            if current_group in get_groups(sp.location.metadata.get('groups', None)) \
                    and not SupplyPointStatus.objects.filter(supply_point=sp._id, status_type=status_type,
                                                             status_date__gte=date).exists():
                if user.get_verified_number():
                    send_sms_to_verified_number(user.get_verified_number(), sms_text)
                    sp_ids.add(sp._id)
    update_statuses(sp_ids, status_type, SupplyPointStatusValues.REMINDER_SENT)

facility_partial = partial(send_for_day, cutoff=5, f=send_ror_reminder)
district_partial = partial(send_for_day, cutoff=13, f=send_ror_reminder, loc_type='DISTRICT')


@periodic_task(run_every=crontab(day_of_month="3-5", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_facility():
    """Last business day before or on 5th day of the Submission month, 8:00am"""
    facility_partial(5)

    
@periodic_task(run_every=crontab(day_of_month="8-10", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_facility():
    """Last business day before or on 10th day of the submission month, 8:00am"""
    facility_partial(10)


@periodic_task(run_every=crontab(day_of_month="10-12", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_facility():
    """Last business day before or on 12th day of the submission month, 8:00am"""
    facility_partial(12)


@periodic_task(run_every=crontab(day_of_month="11-13", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_district():
    district_partial(13)


@periodic_task(run_every=crontab(day_of_month="13-15", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_district():
    district_partial(15)


@periodic_task(run_every=crontab(day_of_month="14-16", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_district():
    district_partial(16)