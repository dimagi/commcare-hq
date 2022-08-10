from datetime import datetime

from django.db import transaction
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from corehq import toggles
from corehq.apps.registry.models import DataRegistry, RegistryInvitation, RegistryGrant, RegistryAuditLog
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
from corehq.apps.users.decorators import require_permission_raw
from corehq.apps.users.models import HqPermissions


def _get_registry_or_404(domain, registry_slug):
    try:
        return DataRegistry.objects.visible_to_domain(domain).get(slug=registry_slug)
    except DataRegistry.DoesNotExist:
        raise Http404


class RegistryPermissionCheck:
    def __init__(self, domain, couch_user):
        self.domain = domain
        self.couch_user = couch_user
        role = couch_user.get_role(domain, allow_enterprise=True)
        self._permissions = role.permissions if role else HqPermissions()
        self.manageable_slugs = set(self._permissions.manage_data_registry_list)

        self.can_manage_all = self._permissions.manage_data_registry
        self.can_manage_some = self.can_manage_all or bool(self.manageable_slugs)

    def can_manage_registry(self, slug):
        return self.can_manage_all or slug in self.manageable_slugs

    def can_view_registry_data(self, slug):
        return (
            self._permissions.view_data_registry_contents
            or slug in self._permissions.view_data_registry_contents_list
        )

    @staticmethod
    def user_can_manage_some(couch_user, domain):
        return RegistryPermissionCheck(domain, couch_user).can_manage_some

    @staticmethod
    def user_can_manage_all(couch_user, domain):
        return RegistryPermissionCheck(domain, couch_user).can_manage_all

    def can_view_some_data_registry_contents(self):
        return self._permissions.view_data_registry_contents or bool(self._permissions.
                                                                     view_data_registry_contents_list)


manage_some_registries_required = require_permission_raw(RegistryPermissionCheck.user_can_manage_some)
manage_all_registries_required = require_permission_raw(RegistryPermissionCheck.user_can_manage_all)


class DataRegistryCrudHelper:
    def __init__(self, domain, registry_slug, request_user):
        self.domain = domain
        self.registry = _get_registry_or_404(domain, registry_slug)
        self.user = request_user

    def check_permission(self, couch_user):
        return RegistryPermissionCheck(self.domain, couch_user).can_manage_registry(self.registry.slug)

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
            data_registry_invitation_created.send(sender=DataRegistry, registry=self.registry, invitation=invitation)
            toggles.DATA_REGISTRY.set(domain, True, namespace=toggles.NAMESPACE_DOMAIN)
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
        data_registry_invitation_removed.send(sender=DataRegistry, registry=self.registry, invitation=invitation)

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
                sender=DataRegistry, registry=self.registry, from_domain=from_domain, to_domains=to_domains
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
            sender=DataRegistry, registry=self.registry, from_domain=from_domain, to_domains=grant.to_domains
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
                sender=DataRegistry, registry=self.registry, invitation=invitation, previous_status=previous_status
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
                sender=DataRegistry, registry=self.registry, invitation=invitation, previous_status=previous_status
            )
        return invitation

    @transaction.atomic
    def delete_registry(self):
        # TODO: figure out what to do here
        self.registry.delete()
        data_registry_deleted.send(sender=DataRegistry, registry=self.registry)


class DataRegistryAuditViewHelper:
    def __init__(self, domain, registry_slug):
        self.domain = domain
        self.registry = _get_registry_or_404(domain, registry_slug)
        self.is_owner = domain == self.registry.domain
        self.filter_kwargs = {}

    def filter(self, domain, start_date, end_date, action):
        if domain:
            self.filter_kwargs["domain"] = domain
        if start_date:
            self.filter_kwargs["date__gte"] = start_date
        if end_date:
            self.filter_kwargs["date__lte"] = datetime.combine(end_date, datetime.max.time())
        if action:
            self.filter_kwargs["action"] = action

    @property
    def query(self):
        query = self.registry.audit_logs.select_related("user")
        if not self.is_owner:
            self.filter_kwargs["domain"] = self.domain
        return query.filter(**self.filter_kwargs)

    def get_logs(self, skip, limit):
        return [log.to_json() for log in self.query[skip:skip + limit]]

    def get_total(self):
        return self.query.count()

    @staticmethod
    def action_options(is_owner):
        options = RegistryAuditLog.ACTION_CHOICES if is_owner else RegistryAuditLog.NON_OWNER_ACTION_CHOICES
        return [
            {"id": option[0], "text": option[1]}
            for option in options
        ]


def get_data_registry_dropdown_options(domain, required_case_types=None, permission_checker=None):
    registries = DataRegistry.objects.visible_to_domain(domain)
    if permission_checker:
        registries = [registry for registry in registries
                      if permission_checker.can_view_registry_data(registry.slug)]

    return [
        {"slug": registry.slug, "name": registry.name}
        for registry in registries
        if not required_case_types or set(registry.wrapped_schema.case_types) & required_case_types
    ]
