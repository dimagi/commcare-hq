from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import jsonfield as old_jsonfield
from corehq.apps.accounting.utils import domain_is_on_trial
from corehq.apps.app_manager.exceptions import XFormIdNotUnique
from corehq.apps.app_manager.models import Form
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.util import form_requires_input, critical_section_for_smsforms_sessions
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.scheduling.models.abstract import Content
from corehq.apps.reminders.models import EmailUsage
from corehq.apps.sms.api import (
    MessageMetadata,
    send_sms,
    send_sms_to_verified_number,
)
from corehq.apps.sms.models import MessagingEvent, PhoneNumber, PhoneBlacklist
from corehq.apps.sms.util import format_message_list, touchforms_error_is_config_error, get_formplayer_exception
from corehq.apps.smsforms.models import SQLXFormsSession
from couchdbkit.resource import ResourceNotFound
from memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from corehq.apps.formplayer_api.smsforms.api import TouchformsError


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

        phone_entry_or_number = self.get_two_way_entry_or_phone_number(recipient)
        if not phone_entry_or_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        message = self.get_translation_from_message_dict(
            logged_event.domain,
            self.message,
            recipient.get_language_code()
        )
        message = self.render_message(message, recipient, logged_subevent)

        self.send_sms_message(logged_event.domain, recipient, phone_entry_or_number, message, logged_subevent)
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
            return None, None, None, None

        if app.domain != domain:
            return None, None, None, None

        return app, module, form, form_requires_input(form)

    def phone_has_opted_out(self, phone_entry_or_number):
        if isinstance(phone_entry_or_number, PhoneNumber):
            pb = PhoneBlacklist.get_by_phone_number_or_none(phone_entry_or_number.phone_number)
        else:
            pb = PhoneBlacklist.get_by_phone_number_or_none(phone_entry_or_number)

        return pb is not None and not pb.send_sms

    def send(self, recipient, logged_event):
        app, module, form, requires_input = self.get_memoized_app_module_form(logged_event.domain)
        if any([o is None for o in (app, module, form)]):
            logged_event.error(MessagingEvent.ERROR_CANNOT_FIND_FORM)
            return

        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )

        # We don't try to look up the phone number from the user case in this scenario
        # because this use case involves starting a survey session, which can be
        # very different if the contact is a user or is a case. So here if recipient
        # is a user we only allow them to fill out the survey as the user contact, and
        # not the user case contact.
        phone_entry_or_number = self.get_two_way_entry_or_phone_number(recipient, try_user_case=False)

        if phone_entry_or_number is None:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        if requires_input and not isinstance(phone_entry_or_number, PhoneNumber):
            logged_subevent.error(MessagingEvent.ERROR_NO_TWO_WAY_PHONE_NUMBER)
            return

        # The SMS framework already checks if the number has opted out before sending to
        # it. But for this use case we check for it here because we don't want to start
        # the survey session if they've opted out.
        if self.phone_has_opted_out(phone_entry_or_number):
            logged_subevent.error(MessagingEvent.ERROR_PHONE_OPTED_OUT)
            return

        with critical_section_for_smsforms_sessions(recipient.get_id):
            # Get the case to submit the form against, if any
            case_id = None
            if is_commcarecase(recipient):
                case_id = recipient.case_id
            elif self.case:
                case_id = self.case.case_id

            if form.requires_case() and not case_id:
                logged_subevent.error(MessagingEvent.ERROR_NO_CASE_GIVEN)
                return

            session, responses = self.start_smsforms_session(
                logged_event.domain,
                recipient,
                case_id,
                phone_entry_or_number,
                logged_subevent,
                self.get_workflow(logged_event),
                app,
                module,
                form
            )

            if session:
                logged_subevent.xforms_session = session
                logged_subevent.save()
                self.send_first_message(
                    logged_event.domain,
                    recipient,
                    phone_entry_or_number,
                    session,
                    responses,
                    logged_subevent,
                    self.get_workflow(logged_event)
                )
                logged_subevent.completed()

    def start_smsforms_session(self, domain, recipient, case_id, phone_entry_or_number, logged_subevent, workflow,
            app, module, form):
        # Close all currently open sessions
        SQLXFormsSession.close_all_open_sms_sessions(domain, recipient.get_id)

        # Start the new session
        try:
            session, responses = start_session(
                SQLXFormsSession.create_session_object(
                    domain,
                    recipient,
                    (phone_entry_or_number.phone_number
                     if isinstance(phone_entry_or_number, PhoneNumber)
                     else phone_entry_or_number),
                    app,
                    form,
                    expire_after=self.expire_after,
                    reminder_intervals=self.reminder_intervals,
                    submit_partially_completed_forms=self.submit_partially_completed_forms,
                    include_case_updates_in_partial_submissions=self.include_case_updates_in_partial_submissions
                ),
                domain,
                recipient,
                app,
                module,
                form,
                case_id,
            )
        except TouchformsError as e:
            logged_subevent.error(
                MessagingEvent.ERROR_TOUCHFORMS_ERROR,
                additional_error_text=get_formplayer_exception(domain, e)
            )

            if touchforms_error_is_config_error(domain, e):
                # Don't reraise the exception because this means there are configuration
                # issues with the form that need to be fixed. The error is logged in the
                # above lines.
                return None, None

            # Reraise the exception so that the framework retries it again later
            raise
        except:
            logged_subevent.error(MessagingEvent.ERROR_TOUCHFORMS_ERROR)
            # Reraise the exception so that the framework retries it again later
            raise

        session.workflow = workflow
        session.save()

        return session, responses

    def send_first_message(self, domain, recipient, phone_entry_or_number, session, responses, logged_subevent,
            workflow):
        if len(responses) > 0:
            message = format_message_list(responses)
            metadata = MessageMetadata(
                workflow=workflow,
                xforms_session_couch_id=session.couch_id,
            )
            if isinstance(phone_entry_or_number, PhoneNumber):
                send_sms_to_verified_number(
                    phone_entry_or_number,
                    message,
                    metadata,
                    logged_subevent=logged_subevent
                )
            else:
                send_sms(
                    domain,
                    recipient,
                    phone_entry_or_number,
                    message,
                    metadata
                )


class IVRSurveyContent(Content):
    form_unique_id = models.CharField(max_length=126)

    def send(self, recipient, logged_event):
        pass


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

        phone_entry_or_number = self.get_two_way_entry_or_phone_number(recipient)
        if not phone_entry_or_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        # An empty list of messages returned from a custom content handler means
        # we shouldn't send anything, so we don't log an error for that.
        for message in self.get_list_of_messages(recipient):
            self.send_sms_message(logged_event.domain, recipient, phone_entry_or_number, message, logged_subevent)

        logged_subevent.completed()
