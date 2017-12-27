from __future__ import absolute_import

from datetime import timedelta, datetime

import pytz
from celery.schedules import crontab
from celery.task import task, periodic_task
from django.conf import settings

from corehq.apps.locations.dbaccessors import (
    generate_user_ids_from_primary_location_ids_from_couch,
    get_location_ids_with_location_type,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.tasks import CELERY_REMINDERS_QUEUE
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from corehq.apps.sms.api import send_sms, MessageMetadata
from corehq.apps.users.models import CommCareUser
from corehq.blobs import get_blob_db
from corehq.form_processor.models import XFormAttachmentSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.timezones.conversions import ServerTime
from custom.icds.const import (
    AWC_LOCATION_TYPE_CODE,
    SUPERVISOR_LOCATION_TYPE_CODE,
    ANDHRA_PRADESH_SITE_CODE,
    MAHARASHTRA_SITE_CODE,
    MADHYA_PRADESH_SITE_CODE,
    BIHAR_SITE_CODE,
    CHHATTISGARH_SITE_CODE,
    JHARKHAND_SITE_CODE,
    RAJASTHAN_SITE_CODE,
    UTTAR_PRADESH_SITE_CODE,
    HINDI,
    TELUGU,
    MARATHI,
)
from custom.icds.messaging.indicators import (
    AWWAggregatePerformanceIndicator,
    AWWSubmissionPerformanceIndicator,
    LSAggregatePerformanceIndicator,
    LSSubmissionPerformanceIndicator,
    LSVHNDSurveyIndicator,
)


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


def get_current_date():
    return ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done().date()


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
    run_every=crontab(hour=9, minute=0),
    queue=settings.CELERY_PERIODIC_QUEUE,
    ignore_result=True
)
def run_user_indicators(phased_rollout=True):
    """
    Runs the weekly / monthly user SMS indicators at 9am IST.
    This task is run every day and the following logic is applied:
        - if it's Monday, the weekly indicators are sent
        - if it's the first of the month, the monthly indicators are sent
        - if it's neither, nothing happens
    """
    current_date = get_current_date()
    is_first_of_month = current_date.day == 1
    is_monday = current_date.weekday() == 0

    if not (is_first_of_month or is_monday):
        return

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

            if is_first_of_month:
                run_indicator.delay(domain, user_id, AWWAggregatePerformanceIndicator, language_code)

            if is_monday:
                run_indicator.delay(domain, user_id, AWWSubmissionPerformanceIndicator, language_code)

        for user_id in generate_user_ids_from_primary_location_ids_from_couch(domain,
                get_supervisor_location_ids(domain)):
            if phased_rollout and user_id not in user_ids_to_send_to:
                continue
            language_code = get_language_code(user_id, telugu_user_ids, marathi_user_ids)

            if is_first_of_month:
                run_indicator.delay(domain, user_id, LSAggregatePerformanceIndicator, language_code)

            if is_monday:
                run_indicator.delay(domain, user_id, LSSubmissionPerformanceIndicator, language_code)
                run_indicator.delay(domain, user_id, LSVHNDSurveyIndicator, language_code)


@periodic_task(run_every=crontab(minute=0, hour='22'))
def delete_old_images():
    if settings.SERVER_ENVIRONMENT not in settings.ICDS_ENVS:
        return

    start = datetime.utcnow()
    max_age = start - timedelta(days=90)
    db = get_blob_db()
    paths = []
    deleted_attachments = []

    def _get_query(db_name, max_age):
        return XFormAttachmentSQL.objects.using(db_name).filter(
            content_type='image/jpeg',
            form__domain='icds-cas',
            form__received_on__lt=max_age
        )

    for db_name in get_db_aliases_for_partitioned_query():
        attachments = _get_query(db_name, max_age)
        while attachments.exists():
            for attachment in attachments[10000]:
                paths.append(db.get_path(attachment.blob_id, attachment.blobdb_bucket()))
                deleted_attachments.append(attachment.pk)

            if paths:
                db.bulk_delete(paths)
                XFormAttachmentSQL.objects.using(db_name).filter(pk__in=deleted_attachments).delete()
                paths = []
                deleted_attachments = []

            attachments = _get_query(db_name, max_age)
