import jsonfield
from corehq.apps.sms.api import send_sms_with_backend_name
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.models.abstract import Content
from corehq.apps.reminders.event_handlers import get_message_template_params
from corehq.apps.reminders.models import Message
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from dimagi.utils.logging import notify_exception
from django.db import models


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
        phone_number = get_one_way_number_for_recipient(recipient)
        if not phone_number or len(phone_number) <= 3:
            # Avoid processing phone numbers that are obviously fake to
            # save on processing time
            return

        language_code = recipient.get_language_code()
        message = self.message.get(language_code) or self.message.get('en')
        message = self.render_message(message, schedule_instance)

        if message:
            send_sms_with_backend_name(recipient.domain, phone_number, message, 'TEST')


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
