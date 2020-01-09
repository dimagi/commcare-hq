import imaplib
import email
import re

from django.conf import settings

from corehq.util.models import BouncedEmail

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
        ]:
            processed_emails.extend(
                self._process_bounced_emails_with_subject(subject)
            )
        return processed_emails

    def _mark_email_as_bounced(self, bounced_email, uid):
        BouncedEmail.objects.update_or_create(
            email=bounced_email,
        )
        if self.delete_processed_messages:
            self._delete_message_with_uid(uid)

    def logout(self):
        self.mail.close()
        self.mail.logout()
