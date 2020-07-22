from corehq.apps.data_vault import VaultStore


class AtomicVaultStore(object):
    def __enter__(self):
        self.vault_entries = []
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is not None and self.vault_entries:
            pks = [vault_entry.pk for vault_entry in self.vault_entries if vault_entry.pk]
            VaultStore.objects.filter(pk__in=pks).delete()

    def save(self, vault_entries):
        self.vault_entries.extend(VaultStore.objects.bulk_create(vault_entries))

    def save_tracked_vault_entries(self, on_model):
        vault_entries = on_model.get_tracked_models_to_create(VaultStore)
        self.save(vault_entries)
