from __future__ import absolute_import
from __future__ import unicode_literals
from celery.task import task
from django.conf import settings
from django.core.mail import send_mail, mail_admins
from corehq.util.log import send_HTML_email
from dimagi.utils.logging import notify_exception
import six


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
    from corehq.util.soft_assert import soft_assert
    soft_assert('{}@dimagi.com'.format('skelly'))(
        all(recipient for recipient in recipient_list),
        'Blank email addresses',
        {
            'subject': subject,
            'message': message,
            'recipients': recipient_list
        }
    )

    recipient_list = [_f for _f in recipient_list if _f]
    if not recipient_list:
        return
    try:
        send_mail(subject, message, from_email, recipient_list,
                  fail_silently=fail_silently, auth_user=auth_user,
                  auth_password=auth_password, connection=connection)
    except Exception as e:
        notify_exception(
            None,
            message="Encountered error while sending email",
            details={
                'subject': subject,
                'recipients': ', '.join(recipient_list),
                'error': e,
            }
        )
        self.retry(exc=e)


@task(queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_html_email_async(self, subject, recipient, html_content,
                          text_content=None, cc=None,
                          email_from=settings.DEFAULT_FROM_EMAIL,
                          file_attachments=None, bcc=None, ga_track=False, ga_tracking_info=None):
    """ Call with send_HTML_email_async.delay(*args, **kwargs)
    - sends emails in the main celery queue
    - if sending fails, retry in 15 min
    - retry a maximum of 10 times
    """
    try:
        send_HTML_email(subject, recipient, html_content,
                        text_content=text_content, cc=cc, email_from=email_from,
                        file_attachments=file_attachments, bcc=bcc, ga_track=ga_track,
                        ga_tracking_info=ga_tracking_info)
    except Exception as e:
        recipient = list(recipient) if not isinstance(recipient, six.string_types) else [recipient]
        notify_exception(
            None,
            message="Encountered error while sending email",
            details={
                'subject': subject,
                'recipients': ', '.join(recipient),
                'error': e,
            }
        )
        self.retry(exc=e)


@task(queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def mail_admins_async(self, subject, message, fail_silently=False, connection=None,
                      html_message=None):
    try:
        mail_admins(subject, message, fail_silently, connection, html_message)
    except Exception as e:
        notify_exception(
            None,
            message="Encountered error while sending email to admins",
            details={
                'subject': subject,
                'error': e,
            }
        )
        self.retry(exc=e)
