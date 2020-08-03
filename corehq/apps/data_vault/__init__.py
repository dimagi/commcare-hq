from corehq.apps.data_vault.utils import get_tracked_vault_entries


def new_vault_entry(value):
    from corehq.apps.data_vault.models import VaultEntry
    return VaultEntry(value=value)


def has_tracked_vault_entries(on_model):
    return bool(get_tracked_vault_entries(on_model))


def save_tracked_vault_entries(on_model):
    from corehq.apps.data_vault.models import VaultEntry
    values = get_tracked_vault_entries(on_model)
    return VaultEntry.objects.bulk_create(values)


__all__ = [
    'new_vault_entry',
    'has_tracked_vault_entries',
    'save_tracked_vault_entries'
]
