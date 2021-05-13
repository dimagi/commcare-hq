import datetime

from celery.schedules import crontab
from celery.task import periodic_task

from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils import log_sso_error, log_sso_info
from corehq.apps.sso.utils.message_helpers import get_idp_cert_expiration_email


IDP_CERT_EXPIRES_REMINDER_DAYS = [30, 15, 7, 3, 1, 0]


@periodic_task(run_every=crontab(minute=0, hour=22), acks_late=True)
def renew_service_provider_x509_certificates():
    """
    This task renews the x509 Service Provider certificates one week before
    they expire (so that there is ample time to respond if there is a problem).
    """
    in_one_week = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    for idp in IdentityProvider.objects.filter(
        sp_rollover_cert_public__isnull=False,
        date_sp_cert_expiration__lte=in_one_week
    ).all():
        idp.renew_service_provider_certificate()


@periodic_task(run_every=crontab(minute=0, hour=22), acks_late=True)
def create_rollover_service_provider_x509_certificates():
    """
    This task creates a rollover x509 Service Provider certificate two
    weeks before it expires.
    """
    in_two_weeks = datetime.datetime.utcnow() + datetime.timedelta(days=14)
    for idp in IdentityProvider.objects.filter(
        sp_rollover_cert_public__isnull=True,
        date_sp_cert_expiration__lte=in_two_weeks
    ).all():
        idp.create_rollover_service_provider_certificate()


@periodic_task(run_every=crontab(minute=0, hour=22), acks_late=True)
def idp_cert_expires_reminder():
    """
    Sends reminder emails for IdP certificates expiring N days from today.
    """
    for num_days in IDP_CERT_EXPIRES_REMINDER_DAYS:
        send_idp_cert_expires_reminder_emails(num_days)


def send_idp_cert_expires_reminder_emails(num_days):
    """
    Sends a reminder email to the enterprise admin email addresses specified on
    the IdP's owner account for any IdPs with certificates that will expire on
    the date `num_days` from today.

    :param num_days: Query IdP certs expiring `num_days` from today.
    """
    today = datetime.datetime.utcnow().date()
    date_in_n_days = today + datetime.timedelta(days=num_days)
    day_after_that = date_in_n_days + datetime.timedelta(days=1)
    queryset = IdentityProvider.objects.filter(
        is_active=True,
        date_idp_cert_expiration__gte=date_in_n_days,
        date_idp_cert_expiration__lt=day_after_that,
    )
    for idp in queryset.all():
        message = get_idp_cert_expiration_email(idp)
        if not message["to"]:
            log_sso_error(f"no admin email addresses for IdP: {idp}")
        try:
            for send_to in message["to"]:
                send_html_email_async.delay(
                    message["subject"],
                    send_to,
                    message["html"],
                    text_content=message["plaintext"],
                    email_from=message["from"],
                    bcc=message["bcc"],
                )
                log_sso_info(
                    "Sent %(num_days)s-day certificate expiration reminder "
                    "email for %(idp_name)s to %(send_to)s." % {
                        "num_days": num_days,
                        "idp_name": idp.name,
                        "send_to": send_to,
                    }
                )
        except Exception as exc:
            log_sso_error(
                f"Error sending cert reminder email for IdP {idp}: {exc!s}",
                show_stack_trace=True,
            )
