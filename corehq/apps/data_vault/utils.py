def _get_tracked_vault_entries(on_model):
    from corehq.apps.data_vault.models import VaultEntry
    return on_model.get_tracked_models_to_create(VaultEntry)
