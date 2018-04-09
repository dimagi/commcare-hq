from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import re
import requests
from smtplib import SMTPSenderRefused
import uuid

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from django.utils.translation import ugettext as _
from requests.exceptions import SSLError

import six
from six.moves.urllib.parse import urlencode


NO_HTML_EMAIL_MESSAGE = """
Your email client is trying to display the plaintext version of an email that
is only supported in HTML. Please set your email client to display this message
in HTML, or use an email client that supports HTML emails.
"""


def send_HTML_email(subject, recipient, html_content, text_content=None,
                    cc=None, email_from=settings.DEFAULT_FROM_EMAIL,
                    file_attachments=None, bcc=None):

    recipient = list(recipient) if not isinstance(recipient, six.string_types) else [recipient]

    if not isinstance(html_content, six.text_type):
        html_content = html_content.decode('utf-8')

    if not text_content:
        text_content = getattr(settings, 'NO_HTML_EMAIL_MESSAGE',
                               NO_HTML_EMAIL_MESSAGE)
    elif not isinstance(text_content, six.text_type):
        text_content = text_content.decode('utf-8')


    from_header = {'From': email_from}  # From-header
    connection = get_connection()
    msg = EmailMultiAlternatives(subject, text_content, email_from,
                                 recipient, headers=from_header,
                                 connection=connection, cc=cc, bcc=bcc)
    for file in (file_attachments or []):
        if file:
            msg.attach(file["title"], file["file_obj"].getvalue(),
                       file["mimetype"])
    msg.attach_alternative(html_content, "text/html")
    try:
        msg.send()
    except SMTPSenderRefused as e:
        error_subject = _('ERROR: Could not send "%(subject)s"') % {
            'subject': subject,
        }

        if e.smtp_code == 552:
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
            recipient,
            headers=from_header,
            connection=connection,
            cc=cc,
            bcc=bcc,
        )
        error_msg.send()
