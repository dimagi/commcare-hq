from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives

NO_HTML_EMAIL_MESSAGE = """
Your email client is trying to display the plaintext version of an email that
is only supported in HTML. Please set your email client to display this message
in HTML, or use an email client that supports HTML emails.
"""

def send_HTML_email(subject, recipient, html_content, text_content=None, cc=None, email_from=None):
    if not text_content:
        text_content = getattr(settings, 'NO_HTML_EMAIL_MESSAGE',
                               NO_HTML_EMAIL_MESSAGE)

    # If you get the return_path header wrong, this may impede mail delivery. It appears that the SMTP server
    # has to recognize the return_path as being valid for the sending host. If we set it to, say, our SMTP
    # server, this will always be the case (as the server is explicitly serving the host).
    if email_from is None:
        #todo: verify that this is even necessary here since it seems like email_return_path == email_from
        email_return_path = getattr(settings, 'EMAIL_RETURN_PATH', None)
        if email_return_path is None:
            email_return_path = settings.EMAIL_LOGIN

        email_from = getattr(settings, 'EMAIL_FROM', None)
        if email_from is None:
            email_from = email_return_path
    else:
        email_return_path = email_from

    from_header = {'From': email_from}  # From-header
    connection = get_connection()
    
    msg = EmailMultiAlternatives(subject, text_content, email_return_path, [recipient], headers=from_header, connection=connection, cc=cc)
    msg.attach_alternative(html_content, "text/html")
    msg.send()
