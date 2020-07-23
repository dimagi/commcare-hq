def add_vault_entry(value):
    from corehq.apps.data_vault.models import VaultEntry
    return VaultEntry(value=value)


def has_tracked_vault_entries(on_model):
    return bool(_get_tracked_vault_entries(on_model))


def save_tracked_vault_entries(on_model):
    from corehq.apps.data_vault.models import VaultEntry
    values = _get_tracked_vault_entries(on_model)
    return VaultEntry.objects.bulk_create(values)


def _get_tracked_vault_entries(on_model):
    from corehq.apps.data_vault.models import VaultEntry
    return on_model.get_tracked_models_to_create(VaultEntry)
