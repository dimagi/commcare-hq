from celery.schedules import crontab
from celery.task import periodic_task
from dimagi.utils.dates import get_business_day_of_month_before

from datetime import datetime
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.reminders import update_status, REMINDER_R_AND_R_FACILITY
from custom.ilsgateway.utils import get_current_group, send_for_all_domains
import settings

def send_ror_facilities_reminder(domain, date):
    current_group = get_current_group()
    for user in CommTrackUser.by_domain(domain):
        if user.location and user.location.location_type == 'FACILITY' and user.is_active:
            sp = SupplyPointCase.get_by_location(user.location)
            if sp.location.metadata['group'] == current_group and not SupplyPointStatus.objects.filter(supply_point=sp._id,
                        status_type=SupplyPointStatusTypes.R_AND_R_FACILITY,
                        status_date__gte=date).exists():
                update_status(sp._id, SupplyPointStatusTypes.R_AND_R_FACILITY,
                SupplyPointStatusValues.REMINDER_SENT)
                if user.get_verified_number():
                    send_sms_to_verified_number(user.get_verified_number(), REMINDER_R_AND_R_FACILITY)



@periodic_task(run_every=crontab(day_of_month="3-5", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_facility():
    """Last business day before or on 5th day of the Submission month, 8:00am"""
    now = datetime.utcnow()
    business_day = get_business_day_of_month_before(now.year, now.month, 5)
    if now.day == business_day.day:
        send_for_all_domains(business_day, send_ror_facilities_reminder)

    
@periodic_task(run_every=crontab(day_of_month="8-10", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_facility():
    """Last business day before or on 10th day of the submission month, 8:00am"""
    now = datetime.utcnow()
    business_day = get_business_day_of_month_before(now.year, now.month, 10)
    if now.day == business_day.day:
        send_for_all_domains(business_day, send_ror_facilities_reminder)
    
@periodic_task(run_every=crontab(day_of_month="10-12", hour=8, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_facility():
    """Last business day before or on 12th day of the submission month, 8:00am"""
    now = datetime.utcnow()
    business_day = get_business_day_of_month_before(now.year, now.month, 12)
    if now.day == business_day.day:
        send_for_all_domains(business_day, send_ror_facilities_reminder)