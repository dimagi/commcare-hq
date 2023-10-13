import random
import uuid
from collections import namedtuple
from datetime import datetime, timedelta

from nose.tools import nottest

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.sms.event_handlers import handle_email_messaging_subevent
from corehq.apps.sms.models import MessagingEvent, MessagingSubEvent, SMS
from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.messaging.scheduling.models import ImmediateBroadcast, EmailContent, AlertSchedule
from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance, AlertScheduleInstance

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

    _, _, sms_and_dict = make_events_for_test(
        domain, message_date, source, status, content_type, recipient_type
    )
    return sms_and_dict


@nottest
def make_events_for_test(
        domain,
        message_date,
        source=MessagingEvent.SOURCE_OTHER,
        status=MessagingEvent.STATUS_COMPLETED,
        content_type=MessagingEvent.CONTENT_SMS,
        recipient_type=MessagingEvent.RECIPIENT_CASE,
        **sms_kwargs):
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
        domain=domain,
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
        additional_error_text=None,
    )
    sms, sms_dict = _make_sms(domain, message_date, subevent, **sms_kwargs)
    return event, subevent, SmsAndDict(sms=sms, sms_dict=sms_dict)


def _make_sms(domain, message_date, subevent, **kwargs):
    sms_dict = get_test_sms_fields(domain, message_date, subevent.pk)
    sms_dict.update(kwargs)
    sms = SMS.objects.create(
        **sms_dict
    )
    return SmsAndDict(sms=sms, sms_dict=sms_dict)


@nottest
def get_test_sms_fields(domain, message_date, subevent_id):
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
        messaging_subevent_id=subevent_id,
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
        couch_id=uuid.uuid4().hex
    )
    return sms_dict


@nottest
def make_simple_sms_for_test(domain, message, error_message=None, **kwargs):
    return SMS.objects.create(
        domain=domain,
        date=datetime.utcnow(),
        direction=OUTGOING,
        text=message,
        error=bool(error_message),
        system_error_message=error_message,
        **kwargs
    )


@nottest
def make_case_rule_sms_for_test(domain, rule_name, utcnow=None):
    rule = AutomaticUpdateRule.objects.create(domain=domain, name=rule_name)
    message_date = utcnow or datetime.utcnow()
    event = MessagingEvent.objects.create(
        domain=domain,
        date=message_date,
        source=MessagingEvent.SOURCE_CASE_RULE,
        source_id=rule.pk,
    )
    subevent = event.create_subevent_for_single_sms(
        recipient_doc_type="CommCareCase",
        recipient_id="case_id_123",
    )
    if utcnow:
        subevent.date = utcnow
        subevent.save()

    sms, _ = _make_sms(domain, message_date, subevent)
    return rule, subevent, sms


@nottest
def make_survey_sms_for_test(domain, rule_name, utcnow=None):
    # It appears that in production, many SMSs don't have a direct link to the
    # triggering event - the connection is roundabout via the xforms_session
    rule = AutomaticUpdateRule.objects.create(domain=domain, name=rule_name)
    xforms_session = SQLXFormsSession.objects.create(
        domain=domain,
        couch_id=uuid.uuid4().hex,
        start_time=datetime.utcnow(),
        modified_time=datetime.utcnow(),
        current_action_due=datetime.utcnow(),
        expire_after=3,
        submission_id="fake_form_submission_id"
    )
    message_date = utcnow or datetime.utcnow()
    event = MessagingEvent.objects.create(
        domain=domain,
        date=message_date,
        source=MessagingEvent.SOURCE_CASE_RULE,
        source_id=rule.pk,
    )
    subevent = event.create_subevent_for_single_sms(
        recipient_doc_type="CommCareUser",
        recipient_id="user_id_xyz",
    )
    subevent.app_id = "fake_app_id"
    subevent.form_name = "fake form name"
    subevent.form_unique_id = "fake_form_id"
    subevent.content_type = MessagingEvent.CONTENT_IVR_SURVEY
    subevent.date = message_date
    subevent.xforms_session = xforms_session
    subevent.save()

    sms, _ = _make_sms(domain, message_date, subevent, xforms_session_couch_id=xforms_session.couch_id)
    return rule, xforms_session, event, sms


@nottest
def make_email_event_for_test(domain, schedule_name, user_ids, utcnow=None):
    content = EmailContent(
        subject={'*': 'New messaging API goes live!'},
        message={'*': 'Check out the new API.'},
    )
    schedule = AlertSchedule.create_simple_alert(domain, content)
    broadcast = ImmediateBroadcast.objects.create(
        domain=domain,
        name=schedule_name,
        schedule=schedule,
        recipients=[
            (ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER, user_id) for user_id in user_ids
        ],
    )
    for user_id in user_ids:
        instance = AlertScheduleInstance.create_for_recipient(
            schedule,
            ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER,
            user_id,
            move_to_next_event_not_in_the_past=False,
        )
        instance.send_current_event_content_to_recipients()

    subevents = {}
    for event in MessagingEvent.objects.filter(source_id=broadcast.id):
        for subevent in MessagingSubEvent.objects.filter(parent=event):
            handle_email_messaging_subevent({
                "eventType": "Delivery",
                "delivery": {"timestamp": "2021-05-27T07:09:42.318Z"}
            }, subevent.id)
            subevent.refresh_from_db()
            subevents[subevent.recipient_id] = subevent
    return subevents
