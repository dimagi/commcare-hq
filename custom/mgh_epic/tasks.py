from django.conf import settings

from celery.schedules import crontab

from corehq.apps.celery import periodic_task

from custom.mgh_epic.sync_epic_appointments import sync_all_appointments_domain

MGH_EPIC_DOMAINS = settings.CUSTOM_DOMAINS_BY_MODULE['custom.mgh_epic']


@periodic_task(run_every=crontab(hour="*", minute=1), queue="background_queue")
def sync_all_epic_appointments():
    for domain in MGH_EPIC_DOMAINS:
        sync_all_appointments_domain(domain)
