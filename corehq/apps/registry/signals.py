from django.dispatch import Signal

data_registry_activated = Signal(providing_args=["registry"])
data_registry_deactivated = Signal(providing_args=["registry"])
data_registry_schema_changed = Signal(providing_args=["registry", "new_schema", "old_schema"])
data_registry_invitation_created = Signal(providing_args=["registry", "invitation"])
data_registry_invitation_removed = Signal(providing_args=["registry", "invitation"])
data_registry_invitation_accepted = Signal(providing_args=["registry", "invitation", "previous_status"])
data_registry_invitation_rejected = Signal(providing_args=["registry", "invitation", "previous_status"])
data_registry_grant_created = Signal(providing_args=["registry", "from_domain", "to_domains"])
data_registry_grant_removed = Signal(providing_args=["registry", "from_domain", "to_domains"])
data_registry_deleted = Signal(providing_args=["registry"])
