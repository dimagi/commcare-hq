from celery.task import task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from dimagi.utils.django.email import send_HTML_email

logger = get_task_logger(__name__)


@task(queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_mail_async(self, subject, message, from_email, recipient_list,
                    fail_silently=False, auth_user=None, auth_password=None,
                    connection=None):
    """ Call with send_mail_async.delay(*args, **kwargs)
    - sends emails in the main celery queue
    - if sending fails, retry in 15 min
    - retry a maximum of 10 times
    """
    try:
        send_mail(subject, message, from_email, recipient_list,
                  fail_silently=fail_silently, auth_user=auth_user,
                  auth_password=auth_password, connection=connection)
    except Exception as e:
        logger.error(
            "Encountered error while sending email titled %(subject)s"
            "to %(recipients)s: %(error)s" % {
                'subject': subject,
                'recipients': ', '.join(recipient_list),
                'error': e,
            })
        self.retry(exc=e)


@task(queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_html_email_async(self, subject, recipient, html_content,
                          text_content=None, cc=None,
                          email_from=settings.DEFAULT_FROM_EMAIL,
                          file_attachments=None, bcc=None):
    """ Call with send_HTML_email_async.delay(*args, **kwargs)
    - sends emails in the main celery queue
    - if sending fails, retry in 15 min
    - retry a maximum of 10 times
    """
    try:
        send_HTML_email(subject, recipient, html_content,
                        text_content=text_content, cc=cc, email_from=email_from,
                        file_attachments=file_attachments, bcc=bcc)
    except Exception as e:
        recipient = list(recipient) if not isinstance(recipient, basestring) else [recipient]
        logger.error(
            "Encountered error while sending email titled %(subject)s"
            "to %(recipients)s: %(error)s" % {
                'subject': subject,
                'recipients': ', '.join(recipient),
                'error': e,
            })
        self.retry(exc=e)
