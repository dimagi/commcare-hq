import imaplib
import email
import json
import re

from django.conf import settings

from corehq.util.email_event_utils import (
    record_permanent_bounce,
    record_complaint,
    record_transient_bounce,
    get_relevant_aws_meta,
)
from corehq.util.metrics import metrics_counter
from corehq.util.models import (
    BouncedEmail,
    BounceType,
    NotificationType,
    TransientBounceEmail,
)
from corehq.util.soft_assert import soft_assert

_bounced_email_soft_assert = soft_assert(
    to=['{}@{}'.format('biyeun+bounces', 'dimagi.com')],
    send_to_ops=False
)

# NOTE: BouncedEmailManager is not guaranteed to work with non-AmazonSES
# bounces and complaints or a non-gmail email that receives these notifications.
# Please check your configuration before moving these properties to settings.
EMAIL_SERVER = 'imap.gmail.com'
BOUNCE_DAEMON = 'MAILER-DAEMON@amazonses.com'
COMPLAINTS_DAEMON = 'complaints@email-abuse.amazonses.com'

# From http://regexlib.com/REDetails.aspx?regexp_id=295
EMAIL_REGEX = r'(([A-Za-z0-9]+_+)|([A-Za-z0-9]+\-+)|([A-Za-z0-9]+\.+)|' \
              r'([A-Za-z0-9]+\++))*[A-Za-z0-9]+@((\w+\-+)|(\w+\.))' \
              r'*\w{1,63}\.[a-zA-Z]{2,6}'

EMAIL_REGEX_VALIDATION = rf'^{EMAIL_REGEX}$'


class BouncedEmailManager(object):

    def __init__(self, delete_processed_messages=True):
        self.delete_processed_messages = delete_processed_messages

    def __enter__(self):
        self.mail = imaplib.IMAP4_SSL(EMAIL_SERVER)
        self.mail.login(
            settings.RETURN_PATH_EMAIL,
            settings.RETURN_PATH_EMAIL_PASSWORD
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mail.close()
        self.mail.logout()

    def _get_messages(self, header_search):
        result, data = self.mail.uid('search', None, header_search)
        if result == 'OK':
            for uid in data[0].split():
                fetch_result, fetched_data = self.mail.uid('fetch', uid, '(RFC822)')
                if fetch_result == 'OK':
                    raw_email = fetched_data[0][1]
                    if isinstance(raw_email, bytes):
                        yield uid, email.message_from_bytes(raw_email)
                    elif isinstance(raw_email, str):
                        yield uid, email.message_from_string(raw_email)
        return []

    @staticmethod
    def _get_message_body(message):
        maintype = message.get_content_maintype()
        parts = []
        if maintype == 'multipart':
            for part in message.get_payload():
                if part.get_content_maintype() == 'text':
                    parts.append(part.get_payload())
        elif maintype == 'text':
            parts.append(message.get_payload())
        return " ".join(parts)

    def _get_message_json(self, message):
        body_text = self._get_message_body(message)
        return json.loads(body_text)

    def _get_aws_info(self, message, uid):
        """
        This gets the most important details from AWS SNS notifications for
        Complaints and Bounces.

        Relevant AWS Dcoumentation:
        https://docs.aws.amazon.com/ses/latest/DeveloperGuide/notification-examples.html

        :param message: raw message
        :param uid: SMTP uid of message
        :return: list of AwsMeta objects
        """
        aws_info = []
        base_info = self._get_message_json(message)

        if base_info.get('notificationType'):
            message_info = base_info
        else:
            message_info = base_info.get('Message')
            if isinstance(message_info, str):
                message_info = json.loads(message_info)

        if not message_info:
            return aws_info

        if message_info['notificationType'] not in [
            NotificationType.BOUNCE,
            NotificationType.COMPLAINT,
        ]:
            metrics_counter(
                'commcare.bounced_email_manager.unknown_notification_type'
            )
            self._label_problem_email(
                uid,
                extra_labels=['UnknownAWSNotificationType']
            )
            _bounced_email_soft_assert(
                False,
                f'[{settings.SERVER_ENVIRONMENT}] '
                f'Unknown AWS Notification Type sent to Inbox. '
            )
        else:
            aws_info = get_relevant_aws_meta(message_info)

        return aws_info

    def _delete_message_with_uid(self, uid):
        self.mail.uid('STORE', uid, '+X-GM-LABELS', '\\Trash')
        self.mail.expunge()

    def _label_problem_email(self, uid, extra_labels=()):
        labels = ['problem']
        labels.extend(extra_labels)
        self.mail.uid('STORE', uid, '+X-GM-LABELS', ' '.join(labels))
        self.mail.expunge()

    def _record_permanent_bounce(self, aws_meta, uid):
        record_permanent_bounce(aws_meta)
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)
        metrics_counter('commcare.bounced_email_manager.permanent_bounce_recorded')

    def _record_transient_bounce(self, aws_meta, uid):
        record_transient_bounce(aws_meta)
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)
        metrics_counter('commcare.bounced_email_manager.transient_bounce_recorded')

    def _handle_undetermined_bounce(self, aws_meta, uid):
        _bounced_email_soft_assert(
            False,
            f'[{settings.SERVER_ENVIRONMENT}] '
            f'Received undetermined bounce from {aws_meta.email}, investigate.'
        )
        self._record_permanent_bounce(aws_meta, uid)

    def _record_complaint(self, aws_meta, uid):
        record_complaint(aws_meta)
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)
        metrics_counter('commcare.bounced_email_manager.complaint_recorded')

    def process_aws_notifications(self):
        self.mail.select('inbox')
        for uid, message in self._get_messages(
            f'(Header Delivered-To "{settings.RETURN_PATH_EMAIL}" '
            f'Subject "AWS Notification Message")'
        ):
            try:
                aws_info = self._get_aws_info(message, uid)
                for aws_meta in aws_info:
                    if aws_meta.notification_type == NotificationType.BOUNCE:
                        if aws_meta.main_type == BounceType.PERMANENT:
                            self._record_permanent_bounce(aws_meta, uid)
                        elif aws_meta.main_type == BounceType.TRANSIENT:
                            self._record_transient_bounce(aws_meta, uid)
                        elif aws_meta.main_type == BounceType.UNDETERMINED:
                            self._handle_undetermined_bounce(aws_meta, uid)
                        else:
                            metrics_counter(
                                'commcare.bounced_email_manager.unexpected_bounce_type'
                            )
                            self._label_problem_email(
                                uid,
                                extra_labels=["UnexpectedBounceType"]
                            )
                            _bounced_email_soft_assert(
                                False,
                                f'[{settings.SERVER_ENVIRONMENT}] '
                                f'Unexpected bounce type received. Check inbox.'
                            )
                    elif aws_meta.notification_type == NotificationType.COMPLAINT:
                        self._record_complaint(aws_meta, uid)
            except Exception:
                metrics_counter('commcare.bounced_email_manager.formatting_issues')
                self._label_problem_email(
                    uid,
                    extra_labels=["FormattingIssues"]
                )

    @staticmethod
    def _get_raw_bounce_recipients(message):
        failed_recipient = message.get('X-Failed-Recipients')
        if failed_recipient:
            return [failed_recipient]

        maintype = message.get_content_maintype()
        if maintype == 'multipart':
            for part in message.get_payload():
                if (part.get('Content-Description') == 'Notification'
                        and part.get('Content-Type') == 'text/plain; charset=us-ascii'):
                    notification = part.get_payload().split('\n')
                    # we can be pretty confident of this email's formatting
                    # as the standard AWS hard bounce notification
                    if 'following recipients' in notification[0]:
                        return [n.rstrip('\r') for n in notification[1:]]

                if part.get_content_maintype() == 'message':
                    for forwarded_message in part.get_payload():
                        original_recipient = forwarded_message.get(
                            'Original-Rcpt-To'
                        ) or forwarded_message.get('To')
                        if original_recipient:
                            # if original_recipient is a list of emails, we
                            # cannot be confident which email is bouncing
                            return [original_recipient]

        subject = message.get('Subject')

        if subject == 'Email Delivery Failure':
            body_text = message.get_payload().split('\n')
            if len(body_text) >= 3 and body_text[2].startswith('-- '):
                return [body_text[2].lstrip('-- ').rstrip('\r')]

        if subject == 'failure notice':
            body_text = message.get_payload().split('\n')
            if len(body_text) >= 5 and 'qmail-send' in body_text[0]:
                return [body_text[4].lstrip('<').rstrip('>:\r')]

    def _handle_raw_transient_bounces(self, uid):
        """
        We will not handle the raw transient bounces by hand because it is
        not possible to reliably obtain the message recipient from these emails.
        """
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)

    def _handle_raw_bounced_recipients(self, recipients, uid):
        for recipient in recipients:
            if recipient.startswith('<'):
                # clean
                recipient = recipient.replace('<', '').replace('>', '')
            bounce_exists = BouncedEmail.objects.filter(
                email=recipient,
            ).exists()
            transient_exists = TransientBounceEmail.objects.filter(
                email=recipient
            ).exists()
            if (
                not (bounce_exists or transient_exists)
                and re.search(EMAIL_REGEX_VALIDATION, recipient)
            ):
                # an email will only show up here if there was no prior
                # SNS notification for it. add the email to the bounce list and
                # mark the email in the bounces inbox for further investigation
                BouncedEmail.objects.update_or_create(
                    email=recipient,
                )
                metrics_counter('commcare.bounced_email_manager.sns_notification_missing')
                self._label_problem_email(
                    uid,
                    extra_labels=["SNSNotificationMissing"]
                )
                _bounced_email_soft_assert(
                    False,
                    f'[{settings.SERVER_ENVIRONMENT}] '
                    f'An email bounced that was not caught by SNS: {recipient}'
                )
            elif not (bounce_exists or transient_exists):
                # this email failed to validate, find out why
                metrics_counter('commcare.bounced_email_manager.validation_failed')
                self._label_problem_email(
                    uid,
                    extra_labels=["ValidationFailed"]
                )
                _bounced_email_soft_assert(
                    False,
                    f'[{settings.SERVER_ENVIRONMENT}] '
                    f'Tried to mark "{recipient}" as BOUNCED and failed '
                    f'because it was not a valid email.'
                )
            elif self.delete_processed_messages:
                self._delete_message_with_uid(uid)

    def _process_raw_messages(self, sender):
        """
        This processes the messages sent directly from known bounce and
        complaints daemons.
        :param sender: a known daemon email (string)
        """
        self.mail.select('inbox')
        for uid, message in self._get_messages(
            f'(Header Delivered-To "{settings.RETURN_PATH_EMAIL}" '
            f'From "{sender}")'
        ):
            if message.get('X-Autoreply') or message.get('Auto-Submitted'):
                self._handle_raw_transient_bounces(uid)
            else:
                recipients = self._get_raw_bounce_recipients(message)
                if recipients:
                    self._handle_raw_bounced_recipients(recipients, uid)
                else:
                    metrics_counter('commcare.bounced_email_manager.recipient_unknown')
                    self._label_problem_email(
                        uid,
                        extra_labels=["RecipientUnknown"]
                    )
                    _bounced_email_soft_assert(
                        False,
                        f'[{settings.SERVER_ENVIRONMENT}] '
                        f'Could not find a bounced email recipients. '
                        f'Check inbox for "RecipientUnknown" tag'
                    )

    def process_daemon_messages(self):
        for sender in [BOUNCE_DAEMON, COMPLAINTS_DAEMON]:
            self._process_raw_messages(sender)

    def logout(self):
        self.mail.close()
        self.mail.logout()
