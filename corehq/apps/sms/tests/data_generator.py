import random
from collections import namedtuple

from corehq.apps.sms.models import MessagingEvent, MessagingSubEvent, SMS
from datetime import datetime, timedelta

SmsAndDict = namedtuple('SmsAndDict', ['sms', 'sms_dict'])


def create_fake_sms(domain, randomize=False):
    if not randomize:
        message_date = datetime(2016, 1, 1, 12, 0)
        source = MessagingEvent.SOURCE_OTHER
        status = MessagingEvent.STATUS_COMPLETED
        content_type = MessagingEvent.CONTENT_SMS
        recipient_type = MessagingEvent.RECIPIENT_CASE
    else:
        message_date = datetime.now()
        source = random.choice(MessagingEvent.SOURCE_CHOICES)[0]
        status = random.choice(MessagingEvent.STATUS_CHOICES)[0]
        content_type = random.choice(MessagingEvent.CONTENT_CHOICES)[0]
        recipient_type = random.choice(MessagingEvent.RECIPIENT_CHOICES)[0]

    event = MessagingEvent.objects.create(
        domain=domain,
        date=message_date,
        source=source,
        source_id=None,
        content_type=content_type,
        app_id=None,
        form_unique_id=None,
        form_name=None,
        status=status,
        error_code=None,
        additional_error_text=None,
        recipient_type=None,
        recipient_id=None
    )
    subevent = MessagingSubEvent.objects.create(
        parent=event,
        date=message_date,
        recipient_type=recipient_type,
        recipient_id=None,
        content_type=content_type,
        app_id=None,
        form_unique_id=None,
        form_name=None,
        xforms_session=None,
        case_id=None,
        status=status,
        error_code=None,
        additional_error_text=None
    )
    # Some of the values here don't apply for a simple outgoing SMS,
    # but the point of this is to just test the serialization and that
    # everything makes it to elasticsearch
    sms_dict = dict(
        domain=domain,
        date=message_date,
        couch_recipient_doc_type='CommCareCase',
        couch_recipient='fake-case-id',
        phone_number='99912345678',
        direction='O',
        error=False,
        system_error_message='n/a',
        system_phone_number='00000',
        backend_api='TEST',
        backend_id='fake-backend-id',
        billed=False,
        workflow='default',
        xforms_session_couch_id='fake-session-couch-id',
        reminder_id='fake-reminder-id',
        location_id='fake-location-id',
        messaging_subevent_id=subevent.pk,
        text='test sms text',
        raw_text='raw text',
        datetime_to_process=message_date - timedelta(minutes=1),
        processed=True,
        num_processing_attempts=1,
        queued_timestamp=message_date - timedelta(minutes=2),
        processed_timestamp=message_date + timedelta(minutes=1),
        domain_scope=domain,
        ignore_opt_out=False,
        backend_message_id='fake-backend-message-id',
        chat_user_id='fake-user-id',
        invalid_survey_response=False,
        fri_message_bank_lookup_completed=True,
        fri_message_bank_message_id='bank-id',
        fri_id='12345',
        fri_risk_profile='X',
        custom_metadata={'a': 'b'},
    )
    sms = SMS.objects.create(
        **sms_dict
    )
    return SmsAndDict(sms=sms, sms_dict=sms_dict)
