from datetime import datetime
from celery.schedules import crontab
from celery.task import periodic_task
from dimagi.utils.dates import get_business_day_of_month_before
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms_to_verified_number, send_sms
from corehq.apps.users.models import CouchUser
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.reminders import update_status, REMINDER_DELIVERY_FACILITY
import settings


def send_delivery_reminder(domain, date):
    #TODO Handle groups from ils
    for user in CommTrackUser.by_domain(domain):
        if user.is_active and user.location and user.location.location_type == 'FACILITY':
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and not SupplyPointStatus.objects.filter(supply_point=sp._id,
                                                           status_type=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                           status_date__gte=date).exists():
                couch_user = CouchUser.wrap(user.to_json())
                update_status(sp._id, SupplyPointStatusTypes.SOH_FACILITY,
                    SupplyPointStatusValues.REMINDER_SENT)
                send_sms(domain, user, couch_user.default_phone_number, REMINDER_DELIVERY_FACILITY)


def send_for_all_domains(date):
    for domain in Domain.get_all():
        #TODO Merge with ILSGateway integration?
        #ilsgateway_config = ILSGatewayConfig.for_domain(domain.name)
        #if ilsgateway_config and ilsgateway_config.enabled:
        send_delivery_reminder(domain.name, date)


@periodic_task(run_every=crontab(day_of_month="13-15", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_delivery_task():
    now = datetime.utcnow()
    date_before = get_business_day_of_month_before(now.year, now.month, 15)
    if now.day == date_before.day:
        send_for_all_domains(date_before)


@periodic_task(run_every=crontab(day_of_month="20-22", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_delivery_task():
    now = datetime.utcnow()
    date_before = get_business_day_of_month_before(now.year, now.month, 22)
    if now.day == date_before.day:
        send_for_all_domains(get_business_day_of_month_before(now.year, now.month, 15))

@periodic_task(run_every=crontab(day_of_month="26-30", hour=14, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_delivery_task():
    now = datetime.utcnow()
    date_before = get_business_day_of_month_before(now.year, now.month, 30)
    if now.day == date_before.day:
        send_for_all_domains(get_business_day_of_month_before(now.year, now.month, 15))