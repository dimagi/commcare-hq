import pytz
from celery.schedules import crontab
from celery.task import task, periodic_task
from corehq.apps.locations.dbaccessors import (
    generate_user_ids_from_primary_location_ids_from_couch,
    get_location_ids_with_location_type,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.tasks import CELERY_REMINDERS_QUEUE
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from corehq.apps.sms.api import send_sms, MessageMetadata
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

ANDHRA_PRADESH_SITE_CODE = '28'
MAHARASHTRA_SITE_CODE = ''
MADHYA_PRADESH_SITE_CODE = '23'
BIHAR_SITE_CODE = '10'
CHHATTISGARH_SITE_CODE = '22'
JHARKHAND_SITE_CODE = '20'
RAJASTHAN_SITE_CODE = '08'
UTTAR_PRADESH_SITE_CODE = ''

ENGLISH = 'en'
HINDI = 'hin'
TELUGU = 'tel'
MARATHI = 'mar'


@task(queue=CELERY_REMINDERS_QUEUE, ignore_result=True)
def run_indicator(domain, user_id, indicator_class, language_code=None):
    """
    Runs the given indicator for the given user and sends the SMS if needed.

    :param domain: The domain the indicator is being run for
    :param user_id: The id of either an AWW or LS CommCareUser
    :param indicator_class: a subclass of AWWIndicator or LSIndicator
    """
    user = CommCareUser.get_by_user_id(user_id, domain=domain)

    # The user's phone number and preferred language is stored on the usercase
    usercase = user.get_usercase()

    phone_number = get_one_way_number_for_recipient(usercase)
    if not phone_number or phone_number == '91':
        # If there is no phone number, don't bother calculating the indicator
        return

    if not language_code:
        language_code = usercase.get_language_code()

    indicator = indicator_class(domain, user)
    messages = indicator.get_messages(language_code=language_code)

    if not isinstance(messages, list):
        raise ValueError("Expected a list of messages")

    metadata = MessageMetadata(custom_metadata={
        'icds_indicator': indicator_class.slug,
    })

    for message in messages:
        send_sms(domain, usercase, phone_number, message, metadata=metadata)


def get_awc_location_ids(domain):
    return get_location_ids_with_location_type(domain, AWC_LOCATION_TYPE_CODE)


def get_supervisor_location_ids(domain):
    return get_location_ids_with_location_type(domain, SUPERVISOR_LOCATION_TYPE_CODE)


def is_first_week_of_month():
    day = ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done().day
    return day >= 1 and day <= 7


def get_user_ids_under_location(domain, site_code):
    if not site_code:
        return set([])

    location = SQLLocation.objects.get(domain=domain, site_code=site_code)
    location_ids = list(location.get_descendants(include_self=False).filter(is_archived=False).location_ids())
    return set(generate_user_ids_from_primary_location_ids_from_couch(domain, location_ids))


def get_language_code(user_id, telugu_user_ids, marathi_user_ids):
    if user_id in telugu_user_ids:
        return TELUGU
    elif user_id in marathi_user_ids:
        return MARATHI
    else:
        return HINDI


@periodic_task(
    run_every=crontab(hour=9, minute=0, day_of_week='tue'),
    queue=settings.CELERY_PERIODIC_QUEUE,
    ignore_result=True
)
def run_weekly_indicators(phased_rollout=True):
    """
    Runs the weekly SMS indicators Monday at 9am IST.
    If it's the first week of the month, also run the monthly indicators.
    """
    first_week_of_month_result = is_first_week_of_month()

    for domain in settings.ICDS_SMS_INDICATOR_DOMAINS:
        telugu_user_ids = get_user_ids_under_location(domain, ANDHRA_PRADESH_SITE_CODE)
        marathi_user_ids = get_user_ids_under_location(domain, MAHARASHTRA_SITE_CODE)
        hindi_user_ids = get_user_ids_under_location(domain, MADHYA_PRADESH_SITE_CODE)
        hindi_user_ids |= get_user_ids_under_location(domain, BIHAR_SITE_CODE)
        hindi_user_ids |= get_user_ids_under_location(domain, CHHATTISGARH_SITE_CODE)
        hindi_user_ids |= get_user_ids_under_location(domain, JHARKHAND_SITE_CODE)
        hindi_user_ids |= get_user_ids_under_location(domain, RAJASTHAN_SITE_CODE)
        hindi_user_ids |= get_user_ids_under_location(domain, UTTAR_PRADESH_SITE_CODE)
        user_ids_to_send_to = marathi_user_ids | telugu_user_ids | hindi_user_ids

        for user_id in generate_user_ids_from_primary_location_ids_from_couch(domain,
                get_awc_location_ids(domain)):
            if phased_rollout and user_id not in user_ids_to_send_to:
                continue
            language_code = get_language_code(user_id, telugu_user_ids, marathi_user_ids)

            if first_week_of_month_result:
                run_indicator.delay(domain, user_id, AWWAggregatePerformanceIndicator, language_code)

            run_indicator.delay(domain, user_id, AWWSubmissionPerformanceIndicator, language_code)

        for user_id in generate_user_ids_from_primary_location_ids_from_couch(domain,
                get_supervisor_location_ids(domain)):
            if phased_rollout and user_id not in user_ids_to_send_to:
                continue
            language_code = get_language_code(user_id, telugu_user_ids, marathi_user_ids)

            if first_week_of_month_result:
                run_indicator.delay(domain, user_id, LSAggregatePerformanceIndicator, language_code)

            run_indicator.delay(domain, user_id, LSSubmissionPerformanceIndicator, language_code)
            run_indicator.delay(domain, user_id, LSVHNDSurveyIndicator, language_code)
