from django.dispatch import receiver
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.sms.models import (SQLMobileBackend, SQLMobileBackendMapping,
    MigrationStatus)
from dimagi.utils.logging import notify_exception


@receiver(commcare_domain_post_save)
def sync_default_backend_mapping(sender, domain, **kwargs):
    try:
        if not MigrationStatus.has_migration_completed(MigrationStatus.MIGRATION_BACKEND):
            return
        _sync_default_backend_mapping(domain)
    except Exception:
        notify_exception(None, message="Error syncing default backend mapping"
                         "for domain" % domain.name)


def _sync_default_backend_mapping(domain):
    mapping_attrs = {
        'is_global': False,
        'domain': domain.name,
        'backend_type': 'SMS',
        'prefix': '*',
    }

    try:
        mapping = SQLMobileBackendMapping.objects.get(**mapping_attrs)
    except SQLMobileBackendMapping.DoesNotExist:
        mapping = None

    if domain.default_sms_backend_id:
        if not mapping:
            mapping = SQLMobileBackendMapping(**mapping_attrs)

        backend = SQLMobileBackend.objects.get(couch_id=domain.default_sms_backend_id)
        mapping.backend = backend
        mapping.save()
    else:
        if mapping:
            mapping.delete()
