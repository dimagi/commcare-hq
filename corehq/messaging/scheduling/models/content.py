from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import jsonfield as old_jsonfield
from corehq.apps.accounting.utils import domain_is_on_trial
from corehq.apps.app_manager.exceptions import XFormIdNotUnique
from corehq.apps.app_manager.models import Form
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.models.abstract import Content
from corehq.apps.reminders.models import EmailUsage
from corehq.apps.sms.models import MessagingEvent
from couchdbkit.resource import ResourceNotFound
from memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models


class SMSContent(Content):
    message = old_jsonfield.JSONField(default=dict)

    def render_message(self, message, recipient, logged_subevent):
        if not message:
            logged_subevent.error(MessagingEvent.ERROR_NO_MESSAGE)
            return None

        renderer = self.get_template_renderer(recipient)
        try:
            return renderer.render(message)
        except:
            logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
            return None

    def send(self, recipient, logged_event):
        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )

        phone_number = self.get_one_way_phone_number(recipient)
        if not phone_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        message = self.get_translation_from_message_dict(
            logged_event.domain,
            self.message,
            recipient.get_language_code()
        )
        message = self.render_message(message, recipient, logged_subevent)

        self.send_sms_message(logged_event.domain, recipient, phone_number, message, logged_subevent)
        logged_subevent.completed()


class EmailContent(Content):
    subject = old_jsonfield.JSONField(default=dict)
    message = old_jsonfield.JSONField(default=dict)

    TRIAL_MAX_EMAILS = 50

    def render_subject_and_message(self, subject, message, recipient):
        renderer = self.get_template_renderer(recipient)
        return renderer.render(subject), renderer.render(message)

    def send(self, recipient, logged_event):
        email_usage = EmailUsage.get_or_create_usage_record(logged_event.domain)
        is_trial = domain_is_on_trial(logged_event.domain)

        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )

        subject = self.get_translation_from_message_dict(
            logged_event.domain,
            self.subject,
            recipient.get_language_code()
        )

        message = self.get_translation_from_message_dict(
            logged_event.domain,
            self.message,
            recipient.get_language_code()
        )

        try:
            subject, message = self.render_subject_and_message(subject, message, recipient)
        except:
            logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
            return

        subject = subject or '(No Subject)'
        if not message:
            logged_subevent.error(MessagingEvent.ERROR_NO_MESSAGE)
            return

        email_address = recipient.get_email()
        if not email_address:
            logged_subevent.error(MessagingEvent.ERROR_NO_EMAIL_ADDRESS)
            return

        if is_trial and EmailUsage.get_total_count(logged_event.domain) >= self.TRIAL_MAX_EMAILS:
            logged_subevent.error(MessagingEvent.ERROR_TRIAL_EMAIL_LIMIT_REACHED)
            return

        send_mail_async.delay(subject, message, settings.DEFAULT_FROM_EMAIL, [email_address])
        email_usage.update_count()
        logged_subevent.completed()


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

    def send(self, recipient, logged_event):
        print('*******************************')
        print('To:', recipient)
        print('SMS Survey: ', self.form_unique_id)
        print('*******************************')


class IVRSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    def send(self, recipient, logged_event):
        print('*******************************')
        print('To:', recipient)
        print('IVR Survey: ', self.form_unique_id)
        print('*******************************')


class CustomContent(Content):
    # Should be a key in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT
    # which points to a function to call at runtime to get a list of
    # messsages to send to the recipient.
    custom_content_id = models.CharField(max_length=126)

    def get_list_of_messages(self, recipient):
        if not self.schedule_instance:
            raise ValueError(
                "Expected CustomContent to be invoked in the context of a "
                "ScheduleInstance. Please pass ScheduleInstance to .set_context()"
            )

        if self.custom_content_id not in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT:
            raise ValueError("Encountered unexpected custom content id %s" % self.custom_content_id)

        custom_function = to_function(
            settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT[self.custom_content_id][0]
        )
        messages = custom_function(recipient, self.schedule_instance)

        if not isinstance(messages, list):
            raise TypeError("Expected content to be a list of messages")

        return messages

    def send(self, recipient, logged_event):
        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )

        phone_number = self.get_one_way_phone_number(recipient)
        if not phone_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        # An empty list of messages returned from a custom content handler means
        # we shouldn't send anything, so we don't log an error for that.
        for message in self.get_list_of_messages(recipient):
            self.send_sms_message(logged_event.domain, recipient, phone_number, message, logged_subevent)

        logged_subevent.completed()
