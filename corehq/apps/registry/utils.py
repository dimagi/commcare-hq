from django.db import transaction
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from corehq.apps.registry.models import DataRegistry, RegistryInvitation, RegistryGrant
from corehq.apps.registry.signals import (
    data_registry_activated,
    data_registry_deactivated,
    data_registry_schema_changed,
    data_registry_invitation_created,
    data_registry_invitation_removed,
    data_registry_invitation_accepted,
    data_registry_invitation_rejected,
    data_registry_grant_created,
    data_registry_grant_removed,
    data_registry_deleted,
)


def _get_registry_or_404(domain, registry_slug):
    try:
        return DataRegistry.objects.visible_to_domain(domain).get(slug=registry_slug)
    except DataRegistry.DoesNotExist:
        raise Http404


class DataRegistryCrudHelper:
    def __init__(self, domain, registry_slug, request_user):
        self.registry = _get_registry_or_404(domain, registry_slug)
        self.user = request_user

    def set_attr(self, attr, value):
        setattr(self.registry, attr, value)
        self.registry.save()

    def set_active_state(self, is_active):
        if is_active:
            self.activate()
        else:
            self.deactivate()

    def activate(self):
        if not self.registry.is_active:
            self.registry.activate(self.user)
            data_registry_activated.send(sender=DataRegistry, registry=self.registry)

    def deactivate(self):
        if self.registry.is_active:
            self.registry.deactivate(self.user)
            data_registry_deactivated.send(sender=DataRegistry, registry=self.registry)

    @transaction.atomic
    def update_schema(self, schema):
        if schema != self.registry.schema:
            old_schema = self.registry.schema
            self.registry.schema = schema
            self.registry.save()
            self.registry.logger.schema_changed(self.user, schema, old_schema)
            data_registry_schema_changed.send(
                sender=DataRegistry, registry=self.registry, new_schema=schema, old_schema=old_schema
            )

    @transaction.atomic
    def get_or_create_invitation(self, domain):
        from corehq.apps.domain.models import Domain
        # TODO: check that domain is part of the same account
        domain_obj = Domain.get_by_name(domain)
        if not domain_obj:
            raise ValueError(f"Domain not found: {domain}")

        invitation, created = self.registry.invitations.get_or_create(domain=domain)
        if created:
            self.registry.logger.invitation_added(self.user, invitation)
            data_registry_invitation_created(sender=DataRegistry, registry=self.registry, initation=invitation)
        return invitation, created

    @transaction.atomic
    def remove_invitation(self, domain, invitation_id):
        try:
            invitation = self.registry.invitations.get(id=invitation_id)
        except RegistryInvitation.DoesNotExist:
            raise Http404

        if invitation.domain != domain:
            raise ValueError()

        invitation.delete()
        self.registry.logger.invitation_removed(self.user, invitation_id, invitation)
        data_registry_invitation_removed.send(sender=DataRegistry, registry=self.registry, initation=invitation)

    @transaction.atomic
    def get_or_create_grant(self, from_domain, to_domains):
        available_domains = set(self.registry.invitations.values_list("domain", flat=True))
        not_invited = set(to_domains) - available_domains
        if not_invited:
            raise ValueError(_("Domains must be invited before grants can be created: {not_invited}").format(
                not_invited=not_invited
            ))

        grant, created = self.registry.grants.get_or_create(from_domain=from_domain, to_domains=to_domains)
        if created:
            self.registry.logger.grant_added(self.user, grant)
            data_registry_grant_created.send(
                sender=DataRegistry, from_domain=from_domain, to_domains=to_domains
            )
        return grant, created

    @transaction.atomic
    def remove_grant(self, from_domain, grant_id):
        try:
            grant = self.registry.grants.get(from_domain=from_domain, id=grant_id)
        except RegistryGrant.DoesNotExist:
            raise Http404

        assert grant.registry_id == self.registry.id
        grant.delete()
        self.registry.logger.grant_removed(self.user, grant_id, grant)
        data_registry_grant_removed.send(
            sender=DataRegistry, from_domain=from_domain, to_domains=grant.to_domains
        )
        return grant

    def accept_invitation(self, domain):
        try:
            invitation = self.registry.invitations.get(domain=domain)
        except RegistryInvitation.DoesNotExist:
            raise Http404

        if not invitation.is_accepted:
            previous_status = invitation.status
            invitation.accept(self.user)
            data_registry_invitation_accepted.send(
                sender=DataRegistry, registry=self.registry, previous_status=previous_status
            )
        return invitation

    def reject_invitation(self, domain):
        try:
            invitation = self.registry.invitations.get(domain=domain)
        except RegistryInvitation.DoesNotExist:
            raise Http404

        if not invitation.is_rejected:
            previous_status = invitation.status
            invitation.reject(self.user)
            data_registry_invitation_rejected.send(
                sender=DataRegistry, registry=self.registry, previous_status=previous_status
            )
        return invitation

    @transaction.atomic
    def delete_registry(self):
        # TODO: figure out what to do here
        self.registry.delete()
        data_registry_deleted.send(sender=DataRegistry, registry=self.registry)
