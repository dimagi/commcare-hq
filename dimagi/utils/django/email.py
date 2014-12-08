from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives

NO_HTML_EMAIL_MESSAGE = """
Your email client is trying to display the plaintext version of an email that
is only supported in HTML. Please set your email client to display this message
in HTML, or use an email client that supports HTML emails.
"""


def send_HTML_email(subject, recipient, html_content, text_content=None,
                    cc=None, email_from=settings.DEFAULT_FROM_EMAIL,
                    file_attachments=None, bcc=None):
    if not text_content:
        text_content = getattr(settings, 'NO_HTML_EMAIL_MESSAGE',
                               NO_HTML_EMAIL_MESSAGE)

    recipient = list(recipient) if not isinstance(recipient, basestring) else [recipient]

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
    msg.send()
