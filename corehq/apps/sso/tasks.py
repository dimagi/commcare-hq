import datetime
import logging

from celery.schedules import crontab

from corehq.apps.celery import periodic_task, task
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.sso.models import IdentityProvider, IdentityProviderProtocol
from corehq.apps.sso.utils.context_helpers import (
    get_api_secret_expiration_email_context,
    get_idp_cert_expiration_email_context,
)
from corehq.apps.users.models import HQApiKey
from django.contrib.auth.models import User
from corehq.sql_db.util import paginate_query
from django.db import router
from django.db.models import Q
from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception

log = logging.getLogger(__name__)


IDP_CERT_EXPIRES_REMINDER_DAYS = [30, 15, 7, 3, 1, 0]
IDP_API_SECRET_EXPIRES_REMINDER_DAYS = [30, 15, 7, 3, 1, 0]


@periodic_task(run_every=crontab(minute=0, hour=22), acks_late=True)
def renew_service_provider_x509_certificates():
    """
    This task renews the x509 Service Provider certificates one week before
    they expire (so that there is ample time to respond if there is a problem).
    """
    in_one_week = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    for idp in IdentityProvider.objects.filter(
        protocol=IdentityProviderProtocol.SAML,
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
        protocol=IdentityProviderProtocol.SAML,
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
        protocol=IdentityProviderProtocol.SAML,
        is_active=True,
        date_idp_cert_expiration__gte=date_in_n_days,
        date_idp_cert_expiration__lt=day_after_that,
    )
    for idp in queryset.all():
        context = get_idp_cert_expiration_email_context(idp)
        if not context["to"]:
            log.error(f"no admin email addresses for IdP: {idp}")
        try:
            for send_to in context["to"]:
                send_html_email_async.delay(
                    context["subject"],
                    send_to,
                    context["html"],
                    text_content=context["plaintext"],
                    email_from=context["from"],
                    bcc=context["bcc"],
                )
                log.info(
                    "Sent %(num_days)s-day certificate expiration reminder "
                    "email for %(idp_name)s to %(send_to)s." % {
                        "num_days": num_days,
                        "idp_name": idp.name,
                        "send_to": send_to,
                    }
                )
        except Exception as exc:
            log.error(
                f"Failed to send cert reminder email for IdP {idp}: {exc!s}",
                exc_info=True,
            )


@task(bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def update_sso_user_api_key_expiration_dates(self, identity_provider_id):
    idp = IdentityProvider.objects.get(id=identity_provider_id)
    enforce_key_expiration_for_idp(idp)


def enforce_key_expiration_for_idp(idp):
    num_updated = 0

    if idp.max_days_until_user_api_key_expiration is None:
        return num_updated

    user_iter = get_users_for_email_domains(idp.get_email_domains())
    max_expiration_date = datetime.datetime.utcnow() + datetime.timedelta(
        days=idp.max_days_until_user_api_key_expiration)
    key_iter = get_keys_expiring_after(user_iter, max_expiration_date)

    for key_chunk in chunked(key_iter, 500):
        batch = []
        for key in key_chunk:
            key.expiration_date = max_expiration_date
            batch.append(key)
        HQApiKey.objects.bulk_update(batch, ['expiration_date'])
        num_updated += len(batch)

    return num_updated


def get_users_for_email_domains(domains):
    user_db = router.db_for_read(User)
    user_batch_size = 500

    for domain in domains:
        query = Q(username__endswith=f'@{domain}')
        yield from paginate_query(user_db, User, query, query_size=user_batch_size)


def get_keys_expiring_after(users, expiration_date):
    has_noncompliant_expiration = Q(expiration_date=None) | Q(expiration_date__gt=expiration_date)

    for user in users:
        yield from user.api_keys(manager='all_objects').filter(has_noncompliant_expiration)


@periodic_task(run_every=crontab(minute=0, hour=14), acks_late=True)
def send_api_token_expiration_reminder():
    """
    Sends reminder emails for IDP api secret expiring N days from today.
    """
    for num_days in IDP_API_SECRET_EXPIRES_REMINDER_DAYS:
        send_api_token_expiration_reminder_emails(num_days)


def send_api_token_expiration_reminder_emails(num_days):
    """
    Sends a reminder email to the enterprise admin email addresses specified on
    the IdP's owner account for any IdPs with api secret that will expire on
    the date `num_days` from today, and have enable_user_deactivation is set to True.

    :param num_days: Query IdP api secret expiring `num_days` from today.
    """
    today = datetime.datetime.utcnow().date()
    date_in_n_days = today + datetime.timedelta(days=num_days)
    day_after_that = date_in_n_days + datetime.timedelta(days=1)
    queryset = IdentityProvider.objects.filter(
        is_active=True,
        enable_user_deactivation=True,
        date_api_secret_expiration__gte=date_in_n_days,
        date_api_secret_expiration__lt=day_after_that,
    )
    for idp in queryset.all():
        context = get_api_secret_expiration_email_context(idp)
        if not context["to"]:
            notify_exception(None, f"no admin email addresses for IdP: {idp}")
        try:
            for send_to in context["to"]:
                send_html_email_async.delay(
                    context["subject"],
                    send_to,
                    context["html"],
                    text_content=context["plaintext"],
                    email_from=context["from"],
                    bcc=context["bcc"],
                )
                log.info(
                    "Sent %(num_days)s-day api secret expiration reminder "
                    "email for %(idp_name)s to %(send_to)s." % {
                        "num_days": num_days,
                        "idp_name": idp.name,
                        "send_to": send_to,
                    }
                )
        except Exception as exc:
            notify_exception(None, f"Failed to send api secret expire reminder email for IdP {idp}: {exc!s}",
                             exc_info=True)
