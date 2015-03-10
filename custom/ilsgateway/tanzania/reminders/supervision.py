import datetime

from celery.schedules import crontab
from celery.task import periodic_task
from custom.ewsghana.utils import send_test_message

from dimagi.utils.dates import get_business_day_of_month
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues, SupplyPointStatus
from custom.ilsgateway.tanzania.reminders import update_statuses, REMINDER_SUPERVISION
from custom.ilsgateway.utils import send_for_all_domains
import settings


def send_supervision_reminder(domain, date, test_list=None):
    sp_ids = set()
    users = CommCareUser.by_domain(domain) if not test_list else test_list
    for user in users:
        location = user.location
        if user.is_active and location and location.location_type == 'FACILITY':
            if not SupplyPointStatus.objects.filter(supply_point=location._id,
                                                    status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                                    status_date__gte=date).exists():
                if user.get_verified_number():
                    if not test_list:
                        send_sms_to_verified_number(user.get_verified_number(), REMINDER_SUPERVISION)
                        sp_ids.add(location._id)
                    else:
                        send_test_message(user.get_verified_number(), REMINDER_SUPERVISION)
    update_statuses(sp_ids, SupplyPointStatusTypes.SUPERVISION_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


@periodic_task(run_every=crontab(day_of_month="26-31", hour=14, minute=15), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def supervision_task():
    now = datetime.datetime.utcnow()
    last_business_day = get_business_day_of_month(month=now.month, year=now.year, count=-1)
    if now.day == last_business_day.day:
        send_for_all_domains(last_business_day, send_supervision_reminder)
