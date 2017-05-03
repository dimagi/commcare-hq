from datetime import datetime, timedelta
from celery.task import task, periodic_task
from celery.schedules import crontab

from django.conf import settings
from django.core.mail import send_mail, mail_admins
from corehq.util.log import send_HTML_email
from dimagi.utils.logging import notify_exception


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
        recipient = list(recipient) if not isinstance(recipient, basestring) else [recipient]
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


@periodic_task(run_every=crontab(hour=0, minute=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def delete_stale_password_hashes():
    from corehq.apps.hqwebapp.models import HashedPasswordLoginAttempt
    from corehq.apps.hqwebapp.utils import HASHED_PASSWORD_EXPIRY

    if settings.ENABLE_PASSWORD_HASHING:
        HashedPasswordLoginAttempt.objects.filter(
            used_at__lte=(datetime.today() - timedelta(HASHED_PASSWORD_EXPIRY))
        ).delete()
