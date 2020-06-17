from smtplib import SMTPDataError

from django.conf import settings
from django.core.mail import mail_admins
from django.core.mail.message import EmailMessage

from celery.schedules import crontab
from celery.task import task, periodic_task

from corehq.util.bounced_email_manager import BouncedEmailManager
from corehq.util.metrics import metrics_gauge_task, metrics_track_errors
from dimagi.utils.django.email import COMMCARE_MESSAGE_ID_HEADER, SES_CONFIGURATION_SET_HEADER
from dimagi.utils.logging import notify_exception

from corehq.util.log import send_HTML_email


@task(serializer='pickle', queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_mail_async(self, subject, message, from_email, recipient_list, messaging_event_id=None):
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

    # todo deal with recipients marked as bounced
    from dimagi.utils.django.email import get_valid_recipients, mark_subevent_bounced
    filtered_recipient_list = get_valid_recipients(recipient_list)
    bounced_recipients = list(set(recipient_list) - set(filtered_recipient_list))
    if bounced_recipients and messaging_event_id:
        mark_subevent_bounced(bounced_recipients, messaging_event_id)

    if not filtered_recipient_list:
        return

    headers = {}
    if messaging_event_id is not None:
        headers[COMMCARE_MESSAGE_ID_HEADER] = messaging_event_id
    if settings.SES_CONFIGURATION_SET is not None:
        headers[SES_CONFIGURATION_SET_HEADER] = settings.SES_CONFIGURATION_SET

    try:
        message = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_email,
            to=filtered_recipient_list,
            headers=headers,
        )
        return message.send()
    except SMTPDataError as e:
        # If the SES configuration has not been properly set up, resend the message
        if (
            "Configuration Set does not exist" in e.smtp_error
            and SES_CONFIGURATION_SET_HEADER in message.extra_headers
        ):
            del message.extra_headers[SES_CONFIGURATION_SET_HEADER]
            message.send()
            notify_exception(None, message="SES Configuration Set missing", details={'error': e})
        else:
            raise
    except Exception as e:
        notify_exception(
            None,
            message="Encountered error while sending email",
            details={
                'subject': subject,
                'recipients': ', '.join(filtered_recipient_list),
                'error': e,
            }
        )
        self.retry(exc=e)


@task(serializer='pickle', queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_html_email_async(self, subject, recipient, html_content,
                          text_content=None, cc=None,
                          email_from=settings.DEFAULT_FROM_EMAIL,
                          file_attachments=None, bcc=None,
                          smtp_exception_skip_list=None,
                          messaging_event_id=None):
    """ Call with send_HTML_email_async.delay(*args, **kwargs)
    - sends emails in the main celery queue
    - if sending fails, retry in 15 min
    - retry a maximum of 10 times
    """
    try:
        send_HTML_email(
            subject,
            recipient,
            html_content,
            text_content=text_content,
            cc=cc,
            email_from=email_from,
            file_attachments=file_attachments,
            bcc=bcc,
            smtp_exception_skip_list=smtp_exception_skip_list,
            messaging_event_id=messaging_event_id
        )
    except Exception as e:
        recipient = list(recipient) if not isinstance(recipient, str) else [recipient]
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


@task(serializer='pickle', queue="email_queue",
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


@periodic_task(run_every=crontab(minute=0, hour=0), queue='background_queue')
def process_bounced_emails():
    if settings.RETURN_PATH_EMAIL and settings.RETURN_PATH_EMAIL_PASSWORD:
        try:
            with BouncedEmailManager(
                delete_processed_messages=True
            ) as bounced_manager, metrics_track_errors('process_bounced_emails_task'):
                bounced_manager.process_aws_notifications()
                bounced_manager.process_daemon_messages()
        except Exception as e:
            notify_exception(
                None,
                message="Encountered error while processing bounced emails",
                details={
                    'error': e,
                }
            )


def get_maintenance_alert_active():
    from corehq.apps.hqwebapp.models import MaintenanceAlert
    return 1 if MaintenanceAlert.get_latest_alert() else 0


metrics_gauge_task('commcare.maintenance_alerts.active', get_maintenance_alert_active,
                   run_every=crontab(minute=1))
