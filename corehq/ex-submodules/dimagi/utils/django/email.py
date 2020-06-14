from smtplib import SMTPDataError, SMTPSenderRefused

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from dimagi.utils.logging import notify_exception
from django.utils.translation import ugettext as _

from corehq.util.metrics import metrics_gauge

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


def get_valid_recipients(recipients):
    """
    This filters out any emails that have reported hard bounces or complaints to
    Amazon SES
    :param recipients: list of recipient emails
    :return: list of recipient emails not marked as bounced
    """
    from corehq.util.models import BouncedEmail
    bounced_emails = BouncedEmail.get_hard_bounced_emails(recipients)
    for bounced_email in bounced_emails:
        try:
            email_domain = bounced_email.split('@')[1]
        except IndexError:
            email_domain = bounced_email
        metrics_gauge('commcare.bounced_email', 1, tags={
            'email_domain': email_domain,
        })
    return [recipient for recipient in recipients if recipient not in bounced_emails]


def send_HTML_email(subject, recipient, html_content, text_content=None,
                    cc=None, email_from=settings.DEFAULT_FROM_EMAIL,
                    file_attachments=None, bcc=None,
                    smtp_exception_skip_list=None, messaging_event_id=None):
    recipients = list(recipient) if not isinstance(recipient, str) else [recipient]
    recipients = get_valid_recipients(recipients)
    if not recipients:
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

    headers = {'From': email_from}  # From-header

    if settings.RETURN_PATH_EMAIL:
        headers['Return-Path'] = settings.RETURN_PATH_EMAIL

    if messaging_event_id is not None:
        headers[COMMCARE_MESSAGE_ID_HEADER] = messaging_event_id
    if settings.SES_CONFIGURATION_SET is not None:
        headers[SES_CONFIGURATION_SET_HEADER] = settings.SES_CONFIGURATION_SET

    connection = get_connection()
    msg = EmailMultiAlternatives(subject, text_content, email_from,
                                 recipients, headers=headers,
                                 connection=connection, cc=cc, bcc=bcc)
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
            "Configuration Set does not exist" in e.smtp_error
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
                email_from,
                recipients,
                headers=headers,
                connection=connection,
                cc=cc,
                bcc=bcc,
            )
            error_msg.send()
