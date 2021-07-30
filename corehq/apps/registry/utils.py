from django.db import transaction
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from corehq.apps.registry.models import DataRegistry, RegistryInvitation, RegistryGrant
from corehq.apps.registry.notifications import send_invitation_email


def _get_registry_or_404(domain, registry_slug):
    try:
        return DataRegistry.objects.visible_to_domain(domain).get(slug=registry_slug)
    except DataRegistry.DoesNotExist:
        raise Http404


class DataRegistryCrudHelper:
    def __init__(self, domain, registry_slug, request_user):
        self.registry = _get_registry_or_404(domain, registry_slug)
        self.user = request_user
        # TODO: fire signals

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

    def deactivate(self):
        if self.registry.is_active:
            self.registry.deactivate(self.user)

    @transaction.atomic
    def update_schema(self, schema):
        if schema != self.registry.schema:
            old_schema = self.registry.schema
            self.registry.schema = schema
            self.registry.save()
            self.registry.logger.schema_changed(self.user, schema, old_schema)

    @transaction.atomic
    def get_or_create_invitation(self, domain):
        from corehq.apps.domain.models import Domain
        # TODO: check that domain is part of the same account
        domain_obj = Domain.get_by_name(domain)
        if not domain_obj:
            raise ValueError(f"Domain not found: {domain}")

        invitation, created = self.registry.invitations.get_or_create(domain=domain)
        if created:
            send_invitation_email(self.registry, invitation)
            self.registry.logger.invitation_added(self.user, invitation)
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
        return grant

    def accept_invitation(self, domain):
        try:
            invitation = self.registry.invitations.get(domain=domain)
        except RegistryInvitation.DoesNotExist:
            raise Http404

        if not invitation.is_accepted:
            invitation.accept(self.user)
        return invitation

    def reject_invitation(self, domain):
        try:
            invitation = self.registry.invitations.get(domain=domain)
        except RegistryInvitation.DoesNotExist:
            raise Http404

        if not invitation.is_rejected:
            invitation.reject(self.user)
        return invitation

    @transaction.atomic
    def delete_registry(self):
        # TODO: figure out what to do here
        self.registry.delete()
