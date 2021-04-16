import datetime

from celery.schedules import crontab
from celery.task import periodic_task

from corehq.apps.sso.models import IdentityProvider


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
