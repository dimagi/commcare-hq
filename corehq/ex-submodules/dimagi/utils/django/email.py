from __future__ import absolute_import
from __future__ import unicode_literals
from smtplib import SMTPSenderRefused

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from django.utils.translation import ugettext as _

import six

NO_HTML_EMAIL_MESSAGE = """
Your email client is trying to display the plaintext version of an email that
is only supported in HTML. Please set your email client to display this message
in HTML, or use an email client that supports HTML emails.
"""

LARGE_FILE_SIZE_ERROR_CODE = 552
# ICDS TCL gateway uses non-standard code
LARGE_FILE_SIZE_ERROR_CODE_ICDS_TCL = 452
LARGE_FILE_SIZE_ERROR_CODES = [LARGE_FILE_SIZE_ERROR_CODE, LARGE_FILE_SIZE_ERROR_CODE_ICDS_TCL]


def send_HTML_email(subject, recipient, html_content, text_content=None,
                    cc=None, email_from=settings.DEFAULT_FROM_EMAIL,
                    file_attachments=None, bcc=None, smtp_exception_skip_list=None):
    print("(PV) send html email 0")
    from corehq.util.python_compatibility import soft_assert_type_text
    if isinstance(recipient, six.string_types):
        print("(PV) send html email 1")
        soft_assert_type_text(recipient)
    print("(PV) send html email 2")
    recipient = list(recipient) if not isinstance(recipient, six.string_types) else [recipient]
    print("(PV) send html email 3")
    if not isinstance(html_content, six.text_type):
        html_content = html_content.decode('utf-8')
        print("(PV) send html email 4")

    if not text_content:
        text_content = getattr(settings, 'NO_HTML_EMAIL_MESSAGE',
                               NO_HTML_EMAIL_MESSAGE)
        print("(PV) send html email 5")
    elif not isinstance(text_content, six.text_type):
        text_content = text_content.decode('utf-8')
        print("(PV) send html email 6")

    print("(PV) send html email 7")
    from_header = {'From': email_from}  # From-header
    print("(PV) send html email 8")
    connection = get_connection()
    print("(PV) send html email 9")
    msg = EmailMultiAlternatives(
        subject, text_content, email_from,
                                 recipient, headers=from_header,
                                 connection=connection, cc=cc, bcc=bcc)
    print("(PV) send html email 10")
    for file in (file_attachments or []):
        print("(PV) send html email 11")
        if file:
            print("(PV) send html email 12")
            msg.attach(file["title"], file["file_obj"].getvalue(),
                       file["mimetype"])
    print("(PV) send html email 13")
    msg.attach_alternative(html_content, "text/html")
    print("(PV) send html email 14")
    try:
        print("(PV) send html email 15")
        msg.send()
        print("(PV) send html email 16")
    except SMTPSenderRefused as e:

        print("(PV) send html email 17")
        if smtp_exception_skip_list and e.smtp_code in smtp_exception_skip_list:
            print("(PV) send html email 18")
            raise e
        else:
            print("(PV) send html email 19")
            error_subject = _('ERROR: Could not send "%(subject)s"') % {
                'subject': subject,
            }
            print("(PV) send html email 20")
            if e.smtp_code in LARGE_FILE_SIZE_ERROR_CODES:
                print("(PV) send html email 21")
                error_text = _('Could not send email: file size is too large.')
            else:
                print("(PV) send html email 22")
                error_text = e.smtp_error
                print("(PV) send html email 23")
            error_text = '%s\n\n%s' % (
                error_text,
                _('Please contact %(support_email)s for assistance.') % {
                    'support_email': settings.SUPPORT_EMAIL,
                },
            )
            print("(PV) send html email 24")

            error_msg = EmailMultiAlternatives(
                error_subject,
                error_text,
                email_from,
                recipient,
                headers=from_header,
                connection=connection,
                cc=cc,
                bcc=bcc,
            )
            print("(PV) send html email 25")
            error_msg.send()
            print("(PV) send html email 26")
