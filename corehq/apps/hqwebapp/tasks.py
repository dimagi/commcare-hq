from smtplib import SMTPDataError

from django.conf import settings
from django.core.mail import mail_admins
from django.core.mail.message import EmailMessage
from django.core.management import call_command
from django.utils.translation import gettext as _
from dimagi.utils.django.email import get_email_configuration

from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab

from dimagi.utils.django.email import (
    COMMCARE_MESSAGE_ID_HEADER,
    SES_CONFIGURATION_SET_HEADER,
)
from dimagi.utils.logging import notify_exception

from corehq.apps.celery import periodic_task, task
from corehq.util.bounced_email_manager import BouncedEmailManager
from corehq.util.email_event_utils import get_bounced_system_emails
from corehq.util.log import send_HTML_email
from corehq.util.metrics import metrics_track_errors
from corehq.util.models import TransientBounceEmail


def mark_subevent_gateway_error(messaging_event_id, error, retrying=False):
    from corehq.apps.sms.models import MessagingEvent, MessagingSubEvent
    try:
        subevent = MessagingSubEvent.objects.get(id=messaging_event_id)
    except MessagingSubEvent.DoesNotExist:
        pass
    else:
        if retrying:
            message = "{}. {}".format(str(error), _("Sending will be retried."))
        else:
            message = "{}. {}".format(str(error), _("Sending aborted."))
        subevent.error(
            MessagingEvent.ERROR_EMAIL_GATEWAY,
            additional_error_text=message
        )


@task(serializer='pickle', queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_mail_async(self, subject, message, recipient_list, from_email=settings.DEFAULT_FROM_EMAIL,
                    messaging_event_id=None, filename: str = None, content=None, domain: str = None,
                    use_domain_gateway=False):
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

    configuration = get_email_configuration(domain, use_domain_gateway, from_email)
    recipient_list = [_f for _f in recipient_list if _f]

    # todo deal with recipients marked as bounced
    from dimagi.utils.django.email import (
        get_valid_recipients,
        mark_local_bounced_email,
    )
    filtered_recipient_list = get_valid_recipients(recipient_list, domain)
    bounced_recipients = list(set(recipient_list) - set(filtered_recipient_list))
    if bounced_recipients and messaging_event_id:
        mark_local_bounced_email(bounced_recipients, messaging_event_id)

    if not filtered_recipient_list:
        return

    headers = {}

    if configuration.return_path_email:
        headers['Return-Path'] = configuration.return_path_email

    if messaging_event_id is not None:
        headers[COMMCARE_MESSAGE_ID_HEADER] = messaging_event_id
    if configuration.SES_configuration_set is not None:
        headers[SES_CONFIGURATION_SET_HEADER] = configuration.SES_configuration_set

    try:
        message = EmailMessage(
            subject=subject,
            body=message,
            from_email=configuration.from_email,
            to=filtered_recipient_list,
            headers=headers,
            connection=configuration.connection
        )
        if filename and content:
            message.attach(filename=filename, content=content)
        return message.send()
    except SMTPDataError as e:
        # If the SES configuration has not been properly set up, resend the message
        if (
            "Configuration Set does not exist" in repr(e.smtp_error)
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
                'messaging_event_id': messaging_event_id,
            }
        )
        if messaging_event_id is not None:
            mark_subevent_gateway_error(messaging_event_id, e, retrying=True)
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            if messaging_event_id is not None:
                mark_subevent_gateway_error(messaging_event_id, e, retrying=False)


@task(serializer='pickle', queue="email_queue",
      bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_html_email_async(self, subject, recipient, html_content,
                          text_content=None, cc=None,
                          email_from=settings.DEFAULT_FROM_EMAIL,
                          file_attachments=None, bcc=None,
                          smtp_exception_skip_list=None,
                          messaging_event_id=None,
                          domain=None,
                          use_domain_gateway=False):
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
            messaging_event_id=messaging_event_id,
            domain=domain,
            use_domain_gateway=use_domain_gateway
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
        try:
            self.retry(exc=e)
            if messaging_event_id is not None:
                mark_subevent_gateway_error(messaging_event_id, e, retrying=True)
        except MaxRetriesExceededError:
            if messaging_event_id is not None:
                mark_subevent_gateway_error(messaging_event_id, e, retrying=False)


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
                bounced_manager.process_daemon_messages()
        except Exception as e:
            notify_exception(
                None,
                message="Encountered error while processing bounced emails",
                details={
                    'error': e,
                }
            )


@periodic_task(run_every=crontab(minute=0, hour=2), queue='background_queue')
def alert_bounced_system_emails():
    bounced_system_emails = get_bounced_system_emails()
    if bounced_system_emails:
        bounced_system_emails = ", ".join(bounced_system_emails)
        mail_admins(
            "[IMPORTANT] System emails were marked as bounced! Please investigate.",
            f"These emails have recorded bounces: {bounced_system_emails}. \n"
            f"Please make sure they are not hard bounced in AWS and follow the "
            f"steps in Confluence to properly un-bounce them. Thanks! \n"
            f"HQ will continue to try sending email, but if AWS has them "
            f"permanently bounced, then these messages will not go "
            f"through and it will continue to negatively affect our bounce "
            f"rate percentage. Be swift!"
        )


@periodic_task(run_every=crontab(minute=0, hour=3), queue='background_queue')
def clean_expired_transient_emails():
    try:
        TransientBounceEmail.delete_expired_bounces()
    except Exception as e:
        notify_exception(
            None,
            message="Encountered error while deleting expired "
                    "transient bounce emails",
            details={
                'error': e,
            }
        )


@periodic_task(run_every=crontab(minute=0, hour=4))
def clear_expired_oauth_tokens():
    # https://django-oauth-toolkit.readthedocs.io/en/latest/management_commands.html#cleartokens
    call_command('cleartokens')
