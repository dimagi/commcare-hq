from django.dispatch import Signal, receiver

from corehq.apps.registry.notifications import (
    send_invitation_email,
    send_invitation_response_email,
    send_grant_email,
)

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


@receiver(data_registry_invitation_created)
def send_invitation_email_receiver(sender, **kwargs):
    send_invitation_email(kwargs["registry"], kwargs["invitation"])


@receiver([data_registry_invitation_accepted, data_registry_invitation_rejected])
def send_invitation_response_email_receiver(sender, **kwargs):
    registry = kwargs["registry"]
    invitation = kwargs["invitation"]
    if invitation.domain == registry.domain:
        # don't send emails for the owning domain's invitation
        return
    send_invitation_response_email(registry, invitation)


@receiver(data_registry_grant_created)
def send_grant_email_receiver(sender, **kwargs):
    send_grant_email(kwargs["registry"], kwargs["from_domain"], kwargs["to_domains"])
