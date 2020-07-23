from corehq.apps.data_vault.models import VaultStore


def add_vault_entry(value, identifier):
    return VaultStore(value=value, identifier=identifier)


def save_tracked_vault_entries(on_model):
    values = on_model.get_tracked_models_to_create(VaultStore)
    VaultStore.objects.bulk_create(values)
