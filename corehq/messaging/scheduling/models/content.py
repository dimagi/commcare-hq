import jsonfield
from corehq.apps.sms.api import send_sms_with_backend_name, send_sms
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.models.abstract import Content
from corehq.apps.reminders.event_handlers import get_message_template_params
from corehq.apps.reminders.models import Message
from corehq.apps.sms.api import MessageMetadata
from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function
from django.conf import settings
from django.db import models


def send_sms_for_schedule_instance(schedule_instance, recipient, phone_number, message):
    if not message:
        return

    metadata = MessageMetadata(
        custom_metadata=schedule_instance.memoized_schedule.custom_metadata,
    )

    if schedule_instance.memoized_schedule.is_test:
        send_sms_with_backend_name(schedule_instance.domain, phone_number, message, 'TEST', metadata=metadata)
    else:
        send_sms(schedule_instance.domain, recipient, phone_number, message, metadata=metadata)


class SMSContent(Content):
    message = jsonfield.JSONField(default=dict)

    def render_message(self, message, schedule_instance):
        from corehq.messaging.scheduling.scheduling_partitioned.models import (
            CaseAlertScheduleInstance,
            CaseTimedScheduleInstance,
        )

        if not message:
            return None

        if isinstance(schedule_instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance)):
            case = CaseAccessors(schedule_instance.domain).get_case(schedule_instance.case_id)
            template_params = get_message_template_params(case)
            try:
                return Message.render(message, **template_params)
            except:
                subject = "[Scheduling] Could not render message"
                notify_exception(None, message=subject, details={
                    'schedule_instance_id': schedule_instance.schedule_instance_id,
                })
                return None

        return message

    def send(self, recipient, schedule_instance):
        phone_number = self.get_one_way_phone_number(recipient)
        if not phone_number:
            return

        language_code = recipient.get_language_code()
        message = (
            self.message.get(language_code) or
            self.message.get(schedule_instance.memoized_schedule.default_language_code)
        )
        message = self.render_message(message, schedule_instance)

        send_sms_for_schedule_instance(schedule_instance, recipient, phone_number, message)


class EmailContent(Content):
    subject = jsonfield.JSONField(default=dict)
    message = jsonfield.JSONField(default=dict)

    def send(self, recipient, schedule_instance):
        print '*******************************'
        print 'To:', recipient
        print 'Subject: ', self.subject
        print 'Message: ', self.message
        print '*******************************'


class SMSSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    # The number of minutes after which the survey expires
    expire_after = models.IntegerField()

    def send(self, recipient, schedule_instance):
        print '*******************************'
        print 'To:', recipient
        print 'SMS Survey: ', self.form_unique_id
        print '*******************************'


class IVRSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    def send(self, recipient, schedule_instance):
        print '*******************************'
        print 'To:', recipient
        print 'IVR Survey: ', self.form_unique_id
        print '*******************************'


class CustomContent(Content):
    # Should be a key in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT
    # which points to a function to call at runtime to get a list of
    # messsages to send to the recipient.
    custom_content_id = models.CharField(max_length=126)

    def send(self, recipient, schedule_instance):
        phone_number = self.get_one_way_phone_number(recipient)
        if not phone_number:
            return

        if self.custom_content_id not in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT:
            raise ValueError("Encountered unexpected custom content id %s" % self.custom_content_id)

        custom_function = to_function(
            settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT[self.custom_content_id]
        )
        content = custom_function(recipient, schedule_instance)

        if not isinstance(content, list):
            raise TypeError("Expected content to be a list of messages")

        # Empty list is ok, we just won't send anything
        for message in content:
            send_sms_for_schedule_instance(schedule_instance, recipient, phone_number, message)
