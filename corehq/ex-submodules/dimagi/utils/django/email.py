from abc import ABC, abstractmethod

from django.conf import settings
from django.core.mail import get_connection as django_get_connection

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
