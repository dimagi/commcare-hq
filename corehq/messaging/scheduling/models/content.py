import os
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.http import Http404
from django.utils.translation import gettext as _

import css_inline
import jsonfield as old_jsonfield
from memoized import memoized

from dimagi.utils.modules import to_function

from corehq import toggles
from corehq.apps.accounting.utils import domain_is_on_trial
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_latest_released_app,
)
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.domain.models import Domain
from corehq.apps.formplayer_api.smsforms.api import TouchformsError
from corehq.apps.hqwebapp.tasks import send_html_email_async, send_mail_async
from corehq.apps.reminders.models import EmailUsage
from corehq.apps.sms.models import (
    Email,
    MessagingEvent,
    PhoneBlacklist,
    PhoneNumber,
)
from corehq.apps.sms.util import (
    get_formplayer_exception,
    touchforms_error_is_config_error,
)
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.smsforms.tasks import send_first_message
from corehq.apps.smsforms.util import (
    critical_section_for_smsforms_sessions,
    form_requires_input,
)
from corehq.apps.users.models import CommCareUser
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.blobs.models import BlobMeta
from corehq.blobs.util import random_url_id
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.fcm.exceptions import FCMTokenValidationException
from corehq.messaging.fcm.utils import FCMUtil
from corehq.messaging.scheduling.exceptions import EmailValidationException
from corehq.messaging.scheduling.models.abstract import Content
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.metrics import metrics_counter
from corehq.util.models import NullJsonField
from corehq.util.view_utils import absolute_reverse


@contextmanager
def no_op_context_manager():
    yield


class SMSContent(Content):
    message = old_jsonfield.JSONField(default=dict)

    def create_copy(self):
        """
        See Content.create_copy() for docstring
        """
        return SMSContent(
            message=deepcopy(self.message),
        )

    def render_message(self, message, recipient, logged_subevent):
        if not message:
            logged_subevent.error(MessagingEvent.ERROR_NO_MESSAGE)
            return None

        renderer = self.get_template_renderer(recipient)
        try:
            return renderer.render(message)
        except Exception:
            logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
            return None

    def send(self, recipient, logged_event, phone_entry=None):
        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )

        phone_entry_or_number = phone_entry or self.get_two_way_entry_or_phone_number(
            recipient, domain_for_toggles=logged_event.domain)
        if not phone_entry_or_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        message = self.get_translation_from_message_dict(
            Domain.get_by_name(logged_event.domain),
            self.message,
            recipient.get_language_code()
        )
        message = self.render_message(message, recipient, logged_subevent)

        self.send_sms_message(logged_event.domain, recipient, phone_entry_or_number, message, logged_subevent)
        logged_subevent.completed()


class EmailContent(Content):
    subject = old_jsonfield.JSONField(default=dict)
    message = old_jsonfield.JSONField(default=dict)
    html_message = NullJsonField(default=dict)

    TRIAL_MAX_EMAILS = 50

    def create_copy(self):
        """
        See Content.create_copy() for docstring
        """
        return EmailContent(
            subject=deepcopy(self.subject),
            message=deepcopy(self.message),
            html_message=deepcopy(self.html_message),
        )

    def render_subject_and_message(self, subject, message, html_message, recipient):
        renderer = self.get_template_renderer(recipient)
        return renderer.render(subject), renderer.render(message), renderer.render(html_message)

    def send(self, recipient, logged_event, phone_entry=None):
        domain = logged_event.domain
        email_usage = EmailUsage.get_or_create_usage_record(domain)
        is_trial = domain_is_on_trial(domain)
        domain_obj = Domain.get_by_name(domain)

        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )

        subject = self.get_translation_from_message_dict(
            domain_obj,
            self.subject,
            recipient.get_language_code()
        )

        message = self.get_translation_from_message_dict(
            domain_obj,
            self.message,
            recipient.get_language_code()
        )

        html_message = ''
        if self.html_message:
            html_message = self.get_translation_from_message_dict(
                domain_obj,
                self.html_message,
                recipient.get_language_code()
            )
            # Add extra css added by CKEditor, and inline css styles from template
            email_css_filepath = os.path.join(
                "corehq", "messaging", "scheduling", "templates", "scheduling", "rich_text_email_styles.css")
            with open(email_css_filepath, 'r') as css_file:
                css_inliner = css_inline.CSSInliner(extra_css=css_file.read())
            html_message = css_inliner.inline(html_message)

        try:
            subject, message, html_message = self.render_subject_and_message(
                subject,
                message,
                html_message,
                recipient
            )
        except Exception:
            logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
            return

        subject = subject or '(No Subject)'
        if not message and not html_message:
            logged_subevent.error(MessagingEvent.ERROR_NO_MESSAGE)
            return

        try:
            email_address = self.get_recipient_email(recipient)
        except EmailValidationException as e:
            logged_subevent.error(e.error_type, additional_error_text=e.additional_text)
            return

        if is_trial and EmailUsage.get_total_count(domain) >= self.TRIAL_MAX_EMAILS:
            logged_subevent.error(MessagingEvent.ERROR_TRIAL_EMAIL_LIMIT_REACHED)
            return

        metrics_counter('commcare.messaging.email.sent', tags={'domain': domain})
        if toggles.RICH_TEXT_EMAILS.enabled(domain) and html_message:
            send_html_email_async.delay(
                subject,
                email_address,
                html_message,
                text_content=message,
                messaging_event_id=logged_subevent.id,
                domain=domain,
                use_domain_gateway=True)
        else:
            send_mail_async.delay(
                subject,
                message,
                [email_address],
                messaging_event_id=logged_subevent.id,
                domain=domain,
                use_domain_gateway=True)

        email = Email(
            domain=domain,
            date=logged_subevent.date_last_activity,  # use date from subevent for consistency
            couch_recipient_doc_type=logged_subevent.recipient_type,
            couch_recipient=logged_subevent.recipient_id,
            messaging_subevent_id=logged_subevent.pk,
            recipient_address=email_address,
            subject=subject,
            body=message,
            html_body=html_message,
        )
        email.save()

        email_usage.update_count()

    def get_recipient_email(self, recipient):
        email_address = recipient.get_email()
        if not email_address:
            raise EmailValidationException(MessagingEvent.ERROR_NO_EMAIL_ADDRESS)

        try:
            validate_email(email_address)
        except ValidationError as exc:
            raise EmailValidationException(MessagingEvent.ERROR_INVALID_EMAIL_ADDRESS, str(exc))

        return email_address


class SMSSurveyContent(Content):
    app_id = models.CharField(max_length=126, null=True)
    form_unique_id = models.CharField(max_length=126)

    # See corehq.apps.smsforms.models.SQLXFormsSession for an
    # explanation of these properties
    expire_after = models.IntegerField()
    reminder_intervals = models.JSONField(default=list)
    submit_partially_completed_forms = models.BooleanField(default=False)
    include_case_updates_in_partial_submissions = models.BooleanField(default=False)

    def create_copy(self):
        """
        See Content.create_copy() for docstring
        """
        return SMSSurveyContent(
            app_id=None,
            form_unique_id=None,
            expire_after=self.expire_after,
            reminder_intervals=deepcopy(self.reminder_intervals),
            submit_partially_completed_forms=self.submit_partially_completed_forms,
            include_case_updates_in_partial_submissions=self.include_case_updates_in_partial_submissions,
        )

    @memoized
    def get_memoized_app_module_form(self, domain):
        try:
            if toggles.SMS_USE_LATEST_DEV_APP.enabled(domain, toggles.NAMESPACE_DOMAIN):
                app = get_app(domain, self.app_id)
            else:
                app = get_latest_released_app(domain, self.app_id)
            form = app.get_form(self.form_unique_id)
            module = form.get_module()
        except (Http404, FormNotFoundException):
            return None, None, None, None

        return app, module, form, form_requires_input(form)

    def phone_has_opted_out(self, phone_entry_or_number):
        if isinstance(phone_entry_or_number, PhoneNumber):
            pb = PhoneBlacklist.get_by_phone_number_or_none(phone_entry_or_number.phone_number)
        else:
            pb = PhoneBlacklist.get_by_phone_number_or_none(phone_entry_or_number)

        return pb is not None and not pb.send_sms

    def get_critical_section(self, recipient):
        if self.critical_section_already_acquired:
            return no_op_context_manager()

        return critical_section_for_smsforms_sessions(recipient.get_id)

    def send(self, recipient, logged_event, phone_entry=None):
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
        phone_entry_or_number = (
            phone_entry
            or self.get_two_way_entry_or_phone_number(
                recipient, try_usercase=False, domain_for_toggles=logged_event.domain)
        )

        if phone_entry_or_number is None:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        if requires_input and not isinstance(phone_entry_or_number, PhoneNumber):
            logged_subevent.error(MessagingEvent.ERROR_NO_TWO_WAY_PHONE_NUMBER)
            return

        with self.get_critical_section(recipient):
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
                form
            )

            if session:
                logged_subevent.xforms_session = session
                logged_subevent.save()
                # send_first_message is a celery task
                # but we first call it synchronously to save resources in the 99% case
                # send_first_message will retry itself as a delayed celery task
                # if there are conflicting sessions preventing it from sending immediately
                send_first_message(
                    logged_event.domain,
                    recipient,
                    phone_entry_or_number,
                    session,
                    responses,
                    logged_subevent,
                    self.get_workflow(logged_event)
                )

    def start_smsforms_session(self, domain, recipient, case_id, phone_entry_or_number, logged_subevent, workflow,
            app, form):
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
                form,
                case_id,
                yield_responses=True
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
        except Exception:
            logged_subevent.error(MessagingEvent.ERROR_TOUCHFORMS_ERROR)
            # Reraise the exception so that the framework retries it again later
            raise

        session.workflow = workflow
        session.save()

        return session, responses


class IVRSurveyContent(Content):
    """
    IVR is no longer supported, but in order to display old configurations we
    need to keep this model around.
    """

    # The unique id of the form that will be used as the IVR Survey
    app_id = models.CharField(max_length=126, null=True)
    form_unique_id = models.CharField(max_length=126)

    # If empty list, this is ignored. Otherwise, this is a list of intervals representing
    # minutes to wait.
    # After waiting the amount of minutes specified by each interval, the framework will
    # check if an outbound IVR call was answered for this event. If not, it will retry
    # the outbound call again.
    reminder_intervals = models.JSONField(default=list)

    # At the end of the IVR call, if this is True, the form will be submitted in its current
    # state regardless if it was completed or not.
    submit_partially_completed_forms = models.BooleanField(default=False)

    # Only matters when submit_partially_completed_forms is True.
    # If True, then case updates will be included in partial form submissions, otherwise
    # they will be excluded.
    include_case_updates_in_partial_submissions = models.BooleanField(default=False)

    # The maximum number of times to attempt asking a question on a phone call
    # before giving up and hanging up. This is meant to prevent long running calls
    # where the user is giving invalid answers or not answering at all.
    max_question_attempts = models.IntegerField(default=5)

    def send(self, recipient, logged_event, phone_entry=None):
        pass


class SMSCallbackContent(Content):
    """
    This use case is no longer supported, but in order to display old configurations we
    need to keep this model around.

    The way that this use case worked was as follows. When the event fires for the
    first time, the SMS message is sent as it is for SMSContent. The recipient is then
    expected to perform a "call back" or "flash back" to the system, where they call
    a phone number, let it ring, and hang up. CommCareHQ records the inbound call when
    this happens.

    Then, for every interval specified by reminder_intervals, the system will wait
    that number of minutes and then check for the expected inbound call from the
    recipient. If the inbound call was received, then no further action is needed.
    If not, the SMS message is sent again. On the last interval, the SMS is not
    sent again and the expected callback event is just closed out.

    The results of the expected call back are stored in an entry in
    corehq.apps.sms.models.ExpectedCallback.
    """

    message = models.JSONField(default=dict)

    # This is a list of intervals representing minutes to wait. It should never be empty.
    # See the explanation above to understand how this is used.
    reminder_intervals = models.JSONField(default=list)

    def send(self, recipient, logged_event, phone_entry=None):
        pass


class CustomContent(Content):
    # Should be a key in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT
    # which points to a function to call at runtime to get a list of
    # messsages to send to the recipient.
    custom_content_id = models.CharField(max_length=126)

    def create_copy(self):
        """
        See Content.create_copy() for docstring
        """
        return CustomContent(
            custom_content_id=self.custom_content_id,
        )

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

    def send(self, recipient, logged_event, phone_entry=None):
        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )

        phone_entry_or_number = self.get_two_way_entry_or_phone_number(
            recipient, domain_for_toggles=logged_event.domain)
        if not phone_entry_or_number:
            logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
            return

        # An empty list of messages returned from a custom content handler means
        # we shouldn't send anything, so we don't log an error for that.
        try:
            for message in self.get_list_of_messages(recipient):
                self.send_sms_message(logged_event.domain, recipient, phone_entry_or_number, message,
                                      logged_subevent)
        except Exception as error:
            logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE, additional_error_text=str(error))
            raise
        logged_subevent.completed()


class FCMNotificationContent(Content):
    ACTION_CHOICES = [
        ('SYNC', _('Background Sync'))
    ]

    MESSAGE_TYPE_NOTIFICATION = 'NOTIFICATION'
    MESSAGE_TYPE_DATA = 'DATA'

    MESSAGE_TYPES = [
        (MESSAGE_TYPE_NOTIFICATION, _('Display Messages')),
        (MESSAGE_TYPE_DATA, _('Data Messages'))
    ]
    # subject and message corresponds to 'title' and 'body' respectively in FCM terms.
    subject = old_jsonfield.JSONField(default=dict)
    message = old_jsonfield.JSONField(default=dict)
    action = models.CharField(null=True, choices=ACTION_CHOICES, max_length=25)
    message_type = models.CharField(choices=MESSAGE_TYPES, max_length=25)

    def create_copy(self):
        """
        See Content.create_copy() for docstring
        """
        return FCMNotificationContent(
            subject=deepcopy(self.subject),
            message=deepcopy(self.message),
            action=self.action,
            message_type=self.message_type
        )

    def render_subject_and_message(self, subject, message, recipient):
        renderer = self.get_template_renderer(recipient)
        return renderer.render(subject), renderer.render(message)

    def build_fcm_data_field(self, recipient):
        data = {}
        if self.action:
            data = {
                'action': self.action,
                'username': recipient.raw_username,
                'domain': recipient.domain,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
        return data

    def send(self, recipient, logged_event, phone_entry=None):
        domain_obj = Domain.get_by_name(logged_event.domain)

        logged_subevent = logged_event.create_subevent_from_contact_and_content(
            recipient,
            self,
            case_id=self.case.case_id if self.case else None,
        )
        subject = message = data = None

        if not settings.FCM_CREDS:
            logged_subevent.error(MessagingEvent.ERROR_FCM_NOT_AVAILABLE)
            return

        if not toggles.FCM_NOTIFICATION.enabled(logged_event.domain):
            logged_subevent.error(MessagingEvent.ERROR_FCM_DOMAIN_NOT_ENABLED)
            return

        if not isinstance(recipient, CommCareUser):
            logged_subevent.error(MessagingEvent.ERROR_FCM_UNSUPPORTED_RECIPIENT)
            return

        if self.message_type == self.MESSAGE_TYPE_NOTIFICATION:
            if not (self.subject or self.message):
                logged_subevent.error(MessagingEvent.ERROR_NO_MESSAGE)
                return

            recipient_language_code = recipient.get_language_code()
            subject = self.get_translation_from_message_dict(
                domain_obj,
                self.subject,
                recipient_language_code
            )

            message = self.get_translation_from_message_dict(
                domain_obj,
                self.message,
                recipient_language_code
            )

            try:
                subject, message = self.render_subject_and_message(subject, message, recipient)
            except Exception:
                logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
                return
        else:
            if not self.action:
                logged_subevent.error(MessagingEvent.ERROR_FCM_NO_ACTION)
                return
            data = self.build_fcm_data_field(recipient)

        try:
            devices_fcm_tokens = self.get_recipient_devices_fcm_tokens(recipient)
        except FCMTokenValidationException as e:
            logged_subevent.error(e.error_type, additional_error_text=e.additional_text)
            return

        result = FCMUtil().send_to_multiple_devices(registration_tokens=devices_fcm_tokens, title=subject,
                                                    body=message, data=data)
        if result.failure_count == len(devices_fcm_tokens):
            logged_subevent.error(MessagingEvent.ERROR_FCM_NOTIFICATION_FAILURE)
            return

        logged_subevent.completed()

    def get_recipient_devices_fcm_tokens(self, recipient):
        devices_fcm_tokens = recipient.get_devices_fcm_tokens()
        if not devices_fcm_tokens:
            raise FCMTokenValidationException(MessagingEvent.ERROR_NO_FCM_TOKENS)
        return devices_fcm_tokens


def _meta_property(name):
    def fget(self):
        return getattr(self._meta, name)
    return property(fget)


class EmailImage(object):
    """EmailImage is a thin wrapper around BlobMeta"""
    id = _meta_property("id")
    domain = _meta_property("parent_id")
    filename = _meta_property("name")
    blob_id = _meta_property("key")
    content_type = _meta_property("content_type")
    content_length = _meta_property("content_length")
    delete_after = _meta_property("expires_on")

    def __init__(self, meta):
        self._meta = meta

    @classmethod
    def get(cls, domain, pk):
        return cls(cls.meta_query(domain).get(pk=pk))

    @classmethod
    def get_by_key(cls, domain, key):
        return cls(cls.meta_query(domain).get(key=key))

    @classmethod
    def get_by_keys(cls, keys, domain=None):
        if domain is None:
            results = []
            for db in get_db_aliases_for_partitioned_query():
                results.extend(cls.db_meta_query(db).filter(key__in=keys).all())
            return [cls(m) for m in results]
        return [cls(m) for m in cls.meta_query(domain).filter(key__in=keys).all()]

    @staticmethod
    def meta_query(domain):
        Q = models.Q
        query = BlobMeta.objects.partitioned_query(domain).filter(
            Q(expires_on__isnull=True) | Q(expires_on__gte=datetime.utcnow()),
            type_code=CODES.email_multimedia,
        ).filter(parent_id=domain)
        return query

    @staticmethod
    def db_meta_query(db):
        Q = models.Q
        query = BlobMeta.objects.using(db).filter(
            Q(expires_on__isnull=True) | Q(expires_on__gte=datetime.utcnow()),
            type_code=CODES.email_multimedia,
        )
        return query

    @classmethod
    def get_all(cls, domain=None):
        if domain is None:
            results = []
            for db in get_db_aliases_for_partitioned_query():
                results.extend(cls.db_meta_query(db).order_by("name"))
            return [cls(meta) for meta in results]
        return [cls(meta) for meta in cls.meta_query(domain).order_by("name")]

    @classmethod
    def get_all_blob_ids(cls):
        results = []
        for db in get_db_aliases_for_partitioned_query():
            results.extend(cls.db_meta_query(db).values_list('key', flat=True))
        return results

    @classmethod
    def get_total_size(cls, domain):
        return cls.meta_query(domain).aggregate(total=models.Sum('content_length'))["total"]

    @classmethod
    def save_blob(cls, file_obj, domain, filename, content_type, delete_after=None):
        return cls(get_blob_db().put(
            file_obj,
            domain=domain,
            parent_id=domain,
            type_code=CODES.email_multimedia,
            name=filename,
            key=random_url_id(16),
            content_type=content_type,
            expires_on=delete_after,
        ))

    def get_blob(self):
        db = get_blob_db()
        try:
            blob = db.get(meta=self._meta)
        except (KeyError, NotFound) as err:
            raise NotFound(str(err))
        return blob

    @classmethod
    def bulk_delete(cls, keys):
        get_blob_db().bulk_delete([c._meta for c in cls.get_by_keys(keys)])

    def delete(self):
        get_blob_db().delete(key=self._meta.key)

    def get_url(self):
        return absolute_reverse("download_messaging_image", args=[self.domain, self.blob_id])

    DoesNotExist = BlobMeta.DoesNotExist
