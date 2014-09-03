from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from dimagi.utils.dates import get_business_day_of_month
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues, SupplyPointStatus
from custom.ilsgateway.reminders import update_statuses, REMINDER_SUPERVISION
from custom.ilsgateway.utils import send_for_all_domains
import settings


def send_supervision_reminder(domain, date):
    sp_ids = set()
    for user in CommTrackUser.by_domain(domain):
        if user.is_active and user.location and user.location.location_type == 'FACILITY':
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and not SupplyPointStatus.objects.filter(supply_point=sp._id,
                                                           status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                                           status_date__gte=date).exists():
                if user.get_verified_number():
                        send_sms_to_verified_number(user.get_verified_number(), REMINDER_SUPERVISION)
                        sp_ids.add(sp._id)
    update_statuses(sp_ids, SupplyPointStatusTypes.SUPERVISION_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


@periodic_task(run_every=crontab(day_of_month="26-31", hour=14, minute=15), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def supervision_task():
    now = datetime.datetime.utcnow()
    last_business_day = get_business_day_of_month(month=now.month, year=now.year, count=-1)
    if now.day == last_business_day.day:
        send_for_all_domains(last_business_day, send_supervision_reminder)