from __future__ import absolute_import
from __future__ import print_function
import jsonfield as old_jsonfield
from corehq.apps.app_manager.exceptions import XFormIdNotUnique
from corehq.apps.app_manager.models import Form
from corehq.apps.sms.api import send_sms_with_backend_name, send_sms
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.models.abstract import Content
from corehq.apps.reminders.event_handlers import get_message_template_params
from corehq.apps.reminders.models import Message
from corehq.apps.sms.api import MessageMetadata
from corehq.apps.sms.models import MessagingEvent
from couchdbkit.resource import ResourceNotFound
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models


def get_sms_custom_metadata(schedule_instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    custom_metadata = {}

    if isinstance(schedule_instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance)):
        custom_metadata['case_id'] = schedule_instance.case_id

    if schedule_instance.memoized_schedule.custom_metadata:
        custom_metadata.update(schedule_instance.memoized_schedule.custom_metadata)

    return custom_metadata


def send_sms_for_schedule_instance(schedule_instance, recipient, phone_number, message, logged_subevent):
    if not message:
        return

    metadata = MessageMetadata(
        custom_metadata=get_sms_custom_metadata(schedule_instance),
        messaging_subevent_id=logged_subevent.pk,
    )

    if schedule_instance.memoized_schedule.is_test:
        send_sms_with_backend_name(schedule_instance.domain, phone_number, message, 'TEST', metadata=metadata)
    else:
        send_sms(schedule_instance.domain, recipient, phone_number, message, metadata=metadata)


class SMSContent(Content):
    message = old_jsonfield.JSONField(default=dict)

    def render_message(self, message, logged_subevent, case=None):
        if not message:
            logged_subevent.error(MessagingEvent.ERROR_NO_MESSAGE)
            return None

        if case:
            template_params = get_message_template_params(case)
            try:
                return Message.render(message, **template_params)
            except:
                logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
                return None

        return message

    def send(self, recipient, schedule_instance, logged_event, case=None):
        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=case.case_id if case else None,
        )

        phone_number = self.get_one_way_phone_number(recipient)
        if not phone_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        message = self.get_translation_from_message_dict(
            self.message,
            schedule_instance.memoized_schedule,
            recipient.get_language_code()
        )
        message = self.render_message(message, logged_subevent, case=case)

        send_sms_for_schedule_instance(schedule_instance, recipient, phone_number, message, logged_subevent)
        logged_subevent.completed()


class EmailContent(Content):
    subject = old_jsonfield.JSONField(default=dict)
    message = old_jsonfield.JSONField(default=dict)

    def send(self, recipient, schedule_instance, logged_event, case=None):
        print('*******************************')
        print('To:', recipient)
        print('Subject: ', self.subject)
        print('Message: ', self.message)
        print('*******************************')


class SMSSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    # See corehq.apps.smsforms.models.SQLXFormsSession for an
    # explanation of these properties
    expire_after = models.IntegerField()
    reminder_intervals = JSONField(default=list)
    submit_partially_completed_forms = models.BooleanField(default=False)
    include_case_updates_in_partial_submissions = models.BooleanField(default=False)

    @memoized
    def get_memoized_app_module_form(self, domain):
        try:
            form = Form.get_form(self.form_unique_id)
            app = form.get_app()
            module = form.get_module()
        except (ResourceNotFound, XFormIdNotUnique):
            return None, None, None

        if app.domain != domain:
            return None, None, None

        return app, module, form

    def send(self, recipient, schedule_instance, logged_event, case=None):
        print('*******************************')
        print('To:', recipient)
        print('SMS Survey: ', self.form_unique_id)
        print('*******************************')


class IVRSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    def send(self, recipient, schedule_instance, logged_event, case=None):
        print('*******************************')
        print('To:', recipient)
        print('IVR Survey: ', self.form_unique_id)
        print('*******************************')


class CustomContent(Content):
    # Should be a key in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT
    # which points to a function to call at runtime to get a list of
    # messsages to send to the recipient.
    custom_content_id = models.CharField(max_length=126)

    def get_list_of_messages(self, recipient, schedule_instance):
        if self.custom_content_id not in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT:
            raise ValueError("Encountered unexpected custom content id %s" % self.custom_content_id)

        custom_function = to_function(
            settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT[self.custom_content_id][0]
        )
        messages = custom_function(recipient, schedule_instance)

        if not isinstance(messages, list):
            raise TypeError("Expected content to be a list of messages")

        return messages

    def send(self, recipient, schedule_instance, logged_event, case=None):
        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=case.case_id if case else None,
        )

        phone_number = self.get_one_way_phone_number(recipient)
        if not phone_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        # An empty list of messages returned from a custom content handler means
        # we shouldn't send anything, so we don't log an error for that.
        for message in self.get_list_of_messages(recipient, schedule_instance):
            send_sms_for_schedule_instance(schedule_instance, recipient, phone_number, message, logged_subevent)

        logged_subevent.completed()
