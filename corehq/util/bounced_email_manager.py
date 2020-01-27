import imaplib
import email
import json
import re

from dateutil.parser import parse as parse_datetime

from django.conf import settings

from corehq.util.models import (
    BouncedEmail,
    BounceType,
    NotificationType,
    PermanentBounceMeta,
    ComplaintBounceMeta,
    TransientBounceEmail,
    AwsMeta,
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

        mail_info = message_info.get('mail', {})
        if message_info['notificationType'] == NotificationType.BOUNCE:
            bounce_info = message_info['bounce']
            for recipient in bounce_info['bouncedRecipients']:
                aws_info.append(AwsMeta(
                    notification_type=message_info['notificationType'],
                    main_type=bounce_info['bounceType'],
                    sub_type=bounce_info['bounceSubType'],
                    timestamp=parse_datetime(bounce_info['timestamp']),
                    email=recipient['emailAddress'],
                    reason=recipient.get('diagnosticCode'),
                    headers=mail_info.get('commonHeaders', {}),
                    destination=mail_info.get('destination', []),
                ))
        elif message_info['notificationType'] == NotificationType.COMPLAINT:
            complaint_info = message_info['complaint']
            for recipient in complaint_info['complainedRecipients']:
                aws_info.append(AwsMeta(
                    notification_type=message_info['notificationType'],
                    main_type=message_info.get('complaintFeedbackType'),
                    sub_type=complaint_info.get('complaintSubType'),
                    timestamp=parse_datetime(complaint_info['timestamp']),
                    email=recipient['emailAddress'],
                    reason=None,
                    headers=mail_info.get('commonHeaders', {}),
                    destination=mail_info.get('destination', []),
                ))
        else:
            self._label_problem_email(
                uid,
                extra_labels=['UnknownAWSNotificationType']
            )
            _bounced_email_soft_assert(
                False,
                f'[{settings.SERVER_ENVIRONMENT}] '
                f'Unknown AWS Notification Type sent to Inbox. '
            )

        return aws_info

    @staticmethod
    def _get_message_recipient(message):
        failed_recipient = message.get('X-Failed-Recipients')
        if failed_recipient:
            return failed_recipient

        maintype = message.get_content_maintype()
        if maintype == 'multipart':
            for part in message.get_payload():
                if part.get_content_maintype() == 'message':
                    for forwarded_message in part.get_payload():
                        original_recipient = forwarded_message.get(
                            'Original-Rcpt-To'
                        ) or forwarded_message.get('To')
                        if original_recipient:
                            return original_recipient

    def _delete_message_with_uid(self, uid):
        self.mail.uid('STORE', uid, '+X-GM-LABELS', '\\Trash')
        self.mail.expunge()

    def _label_problem_email(self, uid, extra_labels=()):
        labels = ['problem']
        labels.extend(extra_labels)
        self.mail.uid('STORE', uid, '+X-GM-LABELS', ' '.join(labels))
        self.mail.expunge()

    def _record_permanent_bounce(self, aws_meta, uid):
        bounced_email, _ = BouncedEmail.objects.update_or_create(
            email=aws_meta.email,
        )
        exists = PermanentBounceMeta.objects.filter(
            bounced_email=bounced_email,
            timestamp=aws_meta.timestamp,
            sub_type=aws_meta.sub_type,
        ).exists()
        if not exists:
            PermanentBounceMeta.objects.create(
                bounced_email=bounced_email,
                timestamp=aws_meta.timestamp,
                sub_type=aws_meta.sub_type,
                headers=aws_meta.headers,
                reason=aws_meta.reason,
                destination=aws_meta.destination,
            )
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)

    def _record_transient_bounce(self, aws_meta, uid):
        exists = TransientBounceEmail.objects.filter(
            email=aws_meta.email,
            timestamp=aws_meta.timestamp,
        ).exists()
        if not exists:
            TransientBounceEmail.objects.create(
                email=aws_meta.email,
                timestamp=aws_meta.timestamp,
                headers=aws_meta.headers,
            )
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)

    def _handle_undetermined_bounce(self, aws_meta, uid):
        _bounced_email_soft_assert(
            False,
            f'[{settings.SERVER_ENVIRONMENT}] '
            f'Received undetermined bounce from {aws_meta.email}, investigate.'
        )
        self._record_permanent_bounce(aws_meta, uid)

    def _record_complaint(self, aws_meta, uid):
        bounced_email, _ = BouncedEmail.objects.update_or_create(
            email=aws_meta.email,
        )
        exists = ComplaintBounceMeta.objects.filter(
            bounced_email=bounced_email,
            timestamp=aws_meta.timestamp,
        ).exists()
        if not exists:
            ComplaintBounceMeta.objects.create(
                bounced_email=bounced_email,
                timestamp=aws_meta.timestamp,
                headers=aws_meta.headers,
                feedback_type=aws_meta.main_type,
                sub_type=aws_meta.sub_type,
                destination=aws_meta.destination,
            )
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)

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
            except Exception as e:
                self._label_problem_email(
                    uid,
                    extra_labels=["FormattingIssues"]
                )
                _bounced_email_soft_assert(
                    False,
                    f'[{settings.SERVER_ENVIRONMENT}] '
                    f'Issue processing AWS Notification Message: {e}'
                )

    def process_complaints(self):
        processed_emails = []

        self.mail.select('inbox')
        for uid, message in self._get_messages(
            f'(Header Delivered-To "{settings.RETURN_PATH_EMAIL}" '
            f'From "{COMPLAINTS_DAEMON}")'
        ):
            complaint_email = self._get_message_recipient(message)
            if complaint_email:
                self._mark_email_as_bounced(complaint_email, uid)
                processed_emails.append(complaint_email)

        return processed_emails

    def _process_bounced_emails_with_subject(self, subject):
        processed_emails = []
        self.mail.select('inbox')
        for uid, message in self._get_messages(
            f'(Header Delivered-To "{settings.RETURN_PATH_EMAIL}" '
            f'Subject "{subject}" '
            f'From "{BOUNCE_DAEMON}")'
        ):
            bounced_email = self._get_message_recipient(message)
            if not bounced_email:
                # fall back to using the REGEX as a last resort, in case these
                # messages don't contain a forwarded email
                email_regex = re.search(
                    EMAIL_REGEX,
                    self._get_message_body(message)
                )
                if email_regex:
                    bounced_email = email_regex.group()

            if bounced_email:
                self._mark_email_as_bounced(bounced_email, uid)
                processed_emails.append(bounced_email)
        return processed_emails

    def process_bounces(self):
        processed_emails = []
        for subject in [
            "Delivery Status Notification (Failure)",
            "Undelivered Mail Returned to Sender",
            "Returned mail: see transcript for details",
            "Undeliverable: Scheduled report from CommCare HQ",
        ]:
            processed_emails.extend(
                self._process_bounced_emails_with_subject(subject)
            )
        return processed_emails

    def _mark_email_as_bounced(self, bounced_email, uid):
        if re.search(EMAIL_REGEX_VALIDATION, bounced_email):
            BouncedEmail.objects.update_or_create(
                email=bounced_email,
            )
            if self.delete_processed_messages:
                self._delete_message_with_uid(uid)
        else:
            _bounced_email_soft_assert(
                False,
                f'[{settings.SERVER_ENVIRONMENT}] '
                f'Tried to mark "{bounced_email}" as BOUNCED and failed.'
            )

    def logout(self):
        self.mail.close()
        self.mail.logout()
