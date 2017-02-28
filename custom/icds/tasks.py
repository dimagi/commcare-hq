import pytz
from celery.schedules import crontab
from celery.task import task, periodic_task
from corehq.apps.locations.dbaccessors import (
    generate_user_ids_from_primary_location_ids,
    get_location_ids_with_location_type,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.tasks import CELERY_REMINDERS_QUEUE
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from corehq.apps.sms.api import send_sms
from corehq.apps.users.models import CommCareUser
from corehq.util.timezones.conversions import ServerTime
from custom.icds.messaging.indicators import (
    AWWAggregatePerformanceIndicator,
    AWWSubmissionPerformanceIndicator,
    LSAggregatePerformanceIndicator,
    LSSubmissionPerformanceIndicator,
    LSVHNDSurveyIndicator,
)
from datetime import datetime
from django.conf import settings

AWC_LOCATION_TYPE_CODE = 'awc'
SUPERVISOR_LOCATION_TYPE_CODE = 'supervisor'


@task(queue=CELERY_REMINDERS_QUEUE, ignore_result=True)
def run_indicator(domain, user_id, indicator_class):
    """
    Runs the given indicator for the given user and sends the SMS if needed.

    :param domain: The domain the indicator is being run for
    :param user_id: The id of either an AWW or LS CommCareUser
    :param indicator_class: a subclass of AWWIndicator or LSIndicator
    """
    user = CommCareUser.get_by_user_id(user_id, domain=domain)
    indicator = indicator_class(domain, user)
    # The user's phone number and preferred language is stored on the usercase
    usercase = user.get_usercase()
    messages = indicator.get_messages(language_code=usercase.get_language_code())

    if not isinstance(messages, list):
        raise ValueError("Expected a list of messages")

    if messages:
        phone_number = get_one_way_number_for_recipient(usercase)
        if not phone_number:
            return

        for message in messages:
            send_sms(domain, usercase, phone_number, message)


def get_awc_location_ids(domain):
    return get_location_ids_with_location_type(domain, AWC_LOCATION_TYPE_CODE)


def get_supervisor_location_ids(domain):
    return get_location_ids_with_location_type(domain, SUPERVISOR_LOCATION_TYPE_CODE)


def is_first_week_of_month():
    day = ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done().day
    return day <= 7


@periodic_task(
    run_every=crontab(hour=3, minute=30, day_of_week='mon'),
    queue=settings.CELERY_PERIODIC_QUEUE,
    ignore_result=True
)
def run_weekly_indicators():
    """
    Runs the weekly SMS indicators at 9am IST.
    If it's the first week of the month, also run the monthly indicators.
    """
    first_week_of_month_result = is_first_week_of_month()

    for domain in settings.ICDS_SMS_INDICATOR_DOMAINS:
        for user_id in generate_user_ids_from_primary_location_ids(domain, get_awc_location_ids(domain)):
            if first_week_of_month_result:
                run_indicator.delay(domain, user_id, AWWAggregatePerformanceIndicator)

            run_indicator.delay(domain, user_id, AWWSubmissionPerformanceIndicator)

        for user_id in generate_user_ids_from_primary_location_ids(domain, get_supervisor_location_ids(domain)):
            if first_week_of_month_result:
                run_indicator.delay(domain, user_id, LSAggregatePerformanceIndicator)

            run_indicator.delay(domain, user_id, LSSubmissionPerformanceIndicator)
            run_indicator.delay(domain, user_id, LSVHNDSurveyIndicator)
