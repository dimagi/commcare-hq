from corehq.apps.data_vault.atomic import AtomicVaultStore  # noqa
from corehq.apps.data_vault.models import VaultStore


def add_vault_entry(value, identifier):
    return VaultStore(value=value, identifier=identifier)
