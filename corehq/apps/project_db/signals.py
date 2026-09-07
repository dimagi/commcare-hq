from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from corehq import toggles
from corehq.apps.data_dictionary.models import CaseProperty, CaseType

from .tasks import schedule_project_db_sync


@receiver(post_save, sender=CaseType)
def case_type_saved(sender, instance, **kwargs):
    _sync_domain(instance.domain)


@receiver(post_save, sender=CaseProperty)
def case_property_saved(sender, instance, **kwargs):
    _sync_domain(instance.case_type.domain)


def _sync_domain(domain):
    if toggles.PROJECT_DB.enabled(domain):
        transaction.on_commit(lambda: schedule_project_db_sync(domain))
