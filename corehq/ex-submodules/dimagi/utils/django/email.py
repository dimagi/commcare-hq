from abc import ABC, abstractmethod
from smtplib import SMTPDataError, SMTPSenderRefused

from django.conf import settings
from django.core.mail import get_connection as django_get_connection
from django.core.mail.message import EmailMultiAlternatives
from dimagi.utils.logging import notify_exception
from django.utils.translation import gettext as _

from corehq.util.metrics import metrics_gauge, metrics_counter
from corehq.util.metrics.const import MPM_LIVESUM

NO_HTML_EMAIL_MESSAGE = """
Your email client is trying to display the plaintext version of an email that
is only supported in HTML. Please set your email client to display this message
in HTML, or use an email client that supports HTML emails.
"""

# This is used to mark messages as bounced, etc. from Amazon's SES email service
COMMCARE_MESSAGE_ID_HEADER = "X-COMMCAREHQ-MESSAGE-ID"
SES_CONFIGURATION_SET_HEADER = "X-SES-CONFIGURATION-SET"

LARGE_FILE_SIZE_ERROR_CODE = 552
# ICDS TCL gateway uses non-standard code
LARGE_FILE_SIZE_ERROR_CODE_ICDS_TCL = 452
LARGE_FILE_SIZE_ERROR_CODES = [LARGE_FILE_SIZE_ERROR_CODE, LARGE_FILE_SIZE_ERROR_CODE_ICDS_TCL]


def mark_local_bounced_email(bounced_addresses, message_id):
    from corehq.apps.sms.models import MessagingEvent, MessagingSubEvent
    from corehq.apps.users.models import Invitation, InvitationStatus
    if isinstance(message_id, str) and Invitation.EMAIL_ID_PREFIX in message_id:
        try:
            invite = Invitation.objects.get(uuid=message_id.split(Invitation.EMAIL_ID_PREFIX)[1])
        except Invitation.DoesNotExist:
            pass
        else:
            invite.email_status = InvitationStatus.BOUNCED
            invite.save()
    else:
        try:
            subevent = MessagingSubEvent.objects.get(id=message_id)
        except MessagingSubEvent.DoesNotExist:
            pass
        else:
            metrics_counter('commcare.messaging.email.preemptively_bounced', len(bounced_addresses), tags={
                'domain': subevent.parent.domain,
            })
            subevent.error(
                MessagingEvent.ERROR_EMAIL_BOUNCED,
                additional_error_text=", ".join(bounced_addresses)
            )


def get_valid_recipients(recipients, domain=None):
    """
    This filters out any emails that have reported hard bounces or complaints to
    Amazon SES
    :param recipients: list of recipient emails
    :return: list of recipient emails not marked as bounced
    """
    from corehq.toggles import BLOCKED_DOMAIN_EMAIL_SENDERS
    if domain and BLOCKED_DOMAIN_EMAIL_SENDERS.enabled(domain):
        # don't sent email if domain is blocked
        metrics_gauge('commcare.bounced_email', len(recipients), tags={
            'email_domain': domain,
        }, multiprocess_mode=MPM_LIVESUM)
        return []

    from corehq.util.models import BouncedEmail
    bounced_emails = BouncedEmail.get_hard_bounced_emails(recipients)
    for bounced_email in bounced_emails:
        try:
            email_domain = bounced_email.split('@')[1]
        except IndexError:
            email_domain = bounced_email
        metrics_gauge('commcare.bounced_email', 1, tags={
            'email_domain': email_domain,
        }, multiprocess_mode=MPM_LIVESUM)
    return [recipient for recipient in recipients if recipient not in bounced_emails]


def send_HTML_email(subject, recipient, html_content, text_content=None,
                    cc=None, email_from=settings.DEFAULT_FROM_EMAIL,
                    file_attachments=None, bcc=None,
                    smtp_exception_skip_list=None, messaging_event_id=None,
                    domain=None, use_domain_gateway=False):
    recipients = list(recipient) if not isinstance(recipient, str) else [recipient]
    filtered_recipients = get_valid_recipients(recipients, domain)
    bounced_addresses = list(set(recipients) - set(filtered_recipients))
    if bounced_addresses and messaging_event_id:
        mark_local_bounced_email(bounced_addresses, messaging_event_id)

    if not filtered_recipients:
        # todo address root issues by throwing a real error to catch upstream
        #  fail silently for now to fix time-sensitive SES issue
        return

    if not isinstance(html_content, str):
        html_content = html_content.decode('utf-8')

    if not text_content:
        text_content = getattr(settings, 'NO_HTML_EMAIL_MESSAGE',
                               NO_HTML_EMAIL_MESSAGE)
    elif not isinstance(text_content, str):
        text_content = text_content.decode('utf-8')
    configuration = get_email_configuration(domain, use_domain_gateway, email_from)
    headers = {'From': configuration.from_email}  # From-header

    if configuration.return_path_email:
        headers['Return-Path'] = configuration.return_path_email

    if messaging_event_id is not None:
        headers[COMMCARE_MESSAGE_ID_HEADER] = messaging_event_id
    if configuration.SES_configuration_set is not None:
        headers[SES_CONFIGURATION_SET_HEADER] = configuration.SES_configuration_set

    msg = EmailMultiAlternatives(subject, text_content, configuration.from_email,
                                 filtered_recipients, headers=headers,
                                 connection=configuration.connection, cc=cc, bcc=bcc)
    for file in (file_attachments or []):
        if file:
            msg.attach(file["title"], file["file_obj"].getvalue(),
                       file["mimetype"])
    msg.attach_alternative(html_content, "text/html")

    try:
        msg.send()
    except SMTPDataError as e:
        # If the SES configuration has not been properly set up, resend the message
        if (
            "Configuration Set does not exist" in repr(e.smtp_error)
            and SES_CONFIGURATION_SET_HEADER in msg.extra_headers
        ):
            del msg.extra_headers[SES_CONFIGURATION_SET_HEADER]
            msg.send()
            notify_exception(None, message="SES Configuration Set missing", details={'error': e})
        else:
            raise
    except SMTPSenderRefused as e:

        if smtp_exception_skip_list and e.smtp_code in smtp_exception_skip_list:
            raise e
        else:
            error_subject = _('ERROR: Could not send "%(subject)s"') % {
                'subject': subject,
            }

            if e.smtp_code in LARGE_FILE_SIZE_ERROR_CODES:
                error_text = _('Could not send email: file size is too large.')
            else:
                error_text = e.smtp_error
            error_text = '%s\n\n%s' % (
                error_text,
                _('Please contact %(support_email)s for assistance.') % {
                    'support_email': settings.SUPPORT_EMAIL,
                },
            )

            error_msg = EmailMultiAlternatives(
                error_subject,
                error_text,
                configuration.from_email,
                filtered_recipients,
                headers=headers,
                connection=configuration.connection,
                cc=cc,
                bcc=bcc,
            )
            error_msg.send()


def get_email_configuration(domain: str, use_domain_gateway: bool = True,
                            from_email: str = settings.DEFAULT_FROM_EMAIL):
    from corehq.apps.email.models import EmailSettings
    if use_domain_gateway:
        try:
            email_setting = EmailSettings.objects.get(domain=domain, use_this_gateway=True)
            return CustomEmailConfiguration(email_setting)
        except EmailSettings.DoesNotExist:
            pass

    return DefaultEmailConfiguration(from_email)


class EmailConfigurationManager(ABC):
    @property
    @abstractmethod
    def from_email(self):
        pass

    @property
    @abstractmethod
    def connection(self):
        pass

    @property
    @abstractmethod
    def SES_configuration_set(self):
        pass

    @property
    @abstractmethod
    def return_path_email(self):
        pass


class DefaultEmailConfiguration(EmailConfigurationManager):
    def __init__(self, from_email: str):
        self._from_email: str = from_email

    @property
    def from_email(self) -> str:
        return self._from_email

    @property
    def connection(self):
        return django_get_connection()

    @property
    def SES_configuration_set(self):
        return settings.SES_CONFIGURATION_SET

    @property
    def return_path_email(self):
        return settings.RETURN_PATH_EMAIL


class CustomEmailConfiguration(EmailConfigurationManager):
    def __init__(self, email_setting):
        from corehq.apps.email.models import EmailSettings
        self._email_setting: EmailSettings = email_setting

    @property
    def from_email(self) -> str:
        return self._email_setting.from_email

    @property
    def connection(self):
        backend_settings = {
            'host': self._email_setting.server,
            'port': self._email_setting.port,
            'username': self._email_setting.username,
            'password': self._email_setting.plaintext_password,
            'use_tls': True,
        }
        backend = "django.core.mail.backends.smtp.EmailBackend"
        return django_get_connection(backend=backend, **backend_settings)

    @property
    def SES_configuration_set(self):
        return self._email_setting.ses_config_set_name if self._email_setting.use_tracking_headers else None

    @property
    def return_path_email(self):
        return self._email_setting.return_path_email
