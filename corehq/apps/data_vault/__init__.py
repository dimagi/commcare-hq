from django.db import router

from corehq.apps.data_vault.models import VaultEntry

VAULT_DB_NAME_FOR_WRITE = router.db_for_write(VaultEntry)


def add_vault_entry(value, identifier):
    return VaultEntry(value=value, identifier=identifier)


def has_tracked_vault_entries(on_model):
    return bool(_get_tracked_vault_entries(on_model))


def save_tracked_vault_entries(on_model):
    values = _get_tracked_vault_entries(on_model)
    return VaultEntry.objects.bulk_create(values)


def _get_tracked_vault_entries(on_model):
    return on_model.get_tracked_models_to_create(VaultEntry)
