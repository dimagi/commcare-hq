from smtplib import SMTPSenderRefused
import uuid
import requests
import re
from urllib import urlencode
from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from django.utils.translation import ugettext as _
from requests.exceptions import SSLError

from dimagi.utils.logging import notify_error
import logging


NO_HTML_EMAIL_MESSAGE = """
Your email client is trying to display the plaintext version of an email that
is only supported in HTML. Please set your email client to display this message
in HTML, or use an email client that supports HTML emails.
"""


def send_HTML_email(subject, recipient, html_content, text_content=None,
                    cc=None, email_from=settings.DEFAULT_FROM_EMAIL,
                    file_attachments=None, bcc=None, ga_track=False, ga_tracking_info=None):

    recipient = list(recipient) if not isinstance(recipient, basestring) else [recipient]

    if not text_content:
        text_content = getattr(settings, 'NO_HTML_EMAIL_MESSAGE',
                               NO_HTML_EMAIL_MESSAGE)
        # this is a temporary spam-catcher, to be removed after fb#178059 is resolved
        if 'commcarehq-support+project@dimagi.com' in recipient:
            notify_error("Found an email causing spammy emails to "
                         "commcare-support+project@dimagi.com. Here's the HTML content of email"
                         "\n {}".format(html_content)
            )

    if ga_track and settings.ANALYTICS_IDS.get('GOOGLE_ANALYTICS_API_ID'):
        ga_data = {
            'v': 1,
            'tid': settings.ANALYTICS_IDS.get('GOOGLE_ANALYTICS_API_ID'),
            'cid': uuid.uuid4().hex,
            'dt': subject.encode('utf-8'),
            't': 'event',
            'ec': 'email'
        }
        extra_data = ga_tracking_info if ga_tracking_info else {}
        ga_data.update(extra_data)
        post_data = urlencode(ga_data)
        url = "https://www.google-analytics.com/collect?" + post_data
        new_content = '<img src="{url}&ea=open"/>\n</body>'.format(url=url)
        html_content, count = re.subn(r'(.*)</body>', r'\1'+new_content, html_content)
        assert count != 0, 'Attempted to add tracking to HTML Email with no closing body tag'

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

    if ga_track and settings.ANALYTICS_IDS.get('GOOGLE_ANALYTICS_API_ID'):
        try:
            try:
                requests.get(url + "&ea=send")
            except SSLError:
                # if we get an ssl error try without verification
                requests.get(url + "&ea=send", verify=False)
        except Exception as e:
            # never fail hard on analytics
            logging.exception(u'Unable to send google analytics request for tracked email: {}'.format(e))
