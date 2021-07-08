from autoslug import AutoSlugField
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from corehq.apps.domain.utils import domain_name_stop_words
from corehq.apps.registry.exceptions import RegistryAccessDenied


def slugify_remove_stops(text):
    words = slugify(text).split('-')
    stop_words = domain_name_stop_words()
    return "-".join([word for word in words if word not in stop_words])


class RegistryManager(models.Manager):

    def owned_by_domain(self, domain, is_active=None):
        query = self.filter(domain=domain)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        return query

    def accessible_to_domain(self, domain, slug=None, has_grants=False):
        """
        :param domain: Domain to get registries for
        :param slug: (optional) Filter registries by slug
        :param has_grants: (optional) Set to 'True' to only include registries for which the domain has grants
        """
        query = (
            self.filter(is_active=True)
            .filter(
                invitations__domain=domain,
                invitations__status=RegistryInvitation.STATUS_ACCEPTED,
            )
        )
        if slug:
            query = query.filter(slug=slug)
        if has_grants:
            query = query.filter(grants__to_domains__contains=[domain])
        return query


class DataRegistry(models.Model):
    domain = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    # slug used for referencing the registry in app suite files, APIs etc.
    slug = AutoSlugField(populate_from='name', unique_with='domain', slugify=slugify_remove_stops)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    schema = JSONField(null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    objects = RegistryManager()

    class Meta:
        unique_together = ('domain', 'slug')

    @transaction.atomic
    def activate(self, user):
        if not self.is_active:
            self.is_active = True
            self.save()
            self.logger.registry_activated(user)

    @transaction.atomic
    def deactivate(self, user):
        if self.is_active:
            self.is_active = False
            self.save()
            self.logger.registry_deactivated(user)

    def get_granted_domains(self, domain):
        self.check_access(domain)
        return set(
            self.grants.filter(to_domains__contains=[domain])
            .values_list('from_domain', flat=True)
        )

    def get_participating_domains(self, requesting_domain):
        return set(self.invitations.filter(
            accepted_on__isnull=False,
            rejected_on__isnull=True
        ).values_list('domain', flat=True))

    def check_access(self, domain):
        if not self.is_active:
            raise RegistryAccessDenied()
        invites = self.invitations.filter(domain=domain)
        if not invites:
            raise RegistryAccessDenied()
        invite = invites[0]
        if invite.status != RegistryInvitation.STATUS_ACCEPTED:
            raise RegistryAccessDenied()
        return True

    def check_ownership(self,domain):
        if self.domain != domain:
            raise RegistryAccessDenied()

    @cached_property
    def logger(self):
        return RegistryAuditHelper(self)


class RegistryInvitation(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_ACCEPTED, _("Accepted")),
        (STATUS_REJECTED, _("Rejected")),
    )
    registry = models.ForeignKey("DataRegistry", related_name="invitations", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        unique_together = ("registry", "domain")

    @transaction.atomic
    def accept(self, user):
        self.status = self.STATUS_ACCEPTED
        self.save()
        self.registry.logger.invitation_accepted(user, self)

    @transaction.atomic
    def reject(self, user):
        self.status = self.STATUS_REJECTED
        self.save()
        self.registry.logger.invitation_rejected(user, self)


class RegistryGrant(models.Model):
    registry = models.ForeignKey("DataRegistry", related_name="grants", on_delete=models.CASCADE)
    from_domain = models.CharField(max_length=255)
    to_domains = ArrayField(models.CharField(max_length=255))


class RegistryPermission(models.Model):
    registry = models.ForeignKey("DataRegistry", related_name="permissions", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    read_only_group_id = models.CharField(max_length=255, null=True)

    class Meta:
        unique_together = ('registry', 'domain')


class RegistryAuditLog(models.Model):
    ACTION_ACTIVATED = "activated"
    ACTION_DEACTIVATED = "deactivated"
    ACTION_INVITATION_ADDED = "invitation_added"
    ACTION_INVITATION_REMOVED = "invitation_removed"
    ACTION_INVITATION_ACCEPTED = "invitation_accepted"
    ACTION_INVITATION_REJECTED = "invitation_rejected"
    ACTION_GRANT_ADDED = "grant_added"
    ACTION_GRANT_REMOVED = "grant_removed"
    ACTION_SCHEMA_CHANGED = "schema"
    ACTION_DATA_ACCESSED = "data_accessed"

    ACTION_CHOICES = (
        (ACTION_ACTIVATED, _("Registry Activated")),
        (ACTION_DEACTIVATED, _("Registry De-activated")),
        (ACTION_INVITATION_ADDED, _("Invitation Added")),
        (ACTION_INVITATION_REMOVED, _("Invitation Revoked")),
        (ACTION_INVITATION_ACCEPTED, _("Invitation Accepted")),
        (ACTION_INVITATION_REJECTED, _("Invitation Rejected")),
        (ACTION_GRANT_ADDED, _("Grant created")),
        (ACTION_GRANT_REMOVED, _("Grant removed")),
        (ACTION_SCHEMA_CHANGED, _("Schema Changed")),
        (ACTION_DATA_ACCESSED, _("Data Accessed")),
    )

    RELATED_OBJECT_REGISTRY = "registry"
    RELATED_OBJECT_INVITATION = "invitation"
    RELATED_OBJECT_GRANT = "grant"
    RELATED_OBJECT_UCR = "ucr"
    RELATED_OBJECT_APPLICATION = "application"  # case search
    RELATED_OBJECT_CHOICES = (
        (RELATED_OBJECT_REGISTRY, _("Data Registry")),
        (RELATED_OBJECT_INVITATION, _("Invitation")),
        (RELATED_OBJECT_GRANT, _("Grant")),
        (RELATED_OBJECT_UCR, _("Report")),
        (RELATED_OBJECT_APPLICATION, _("Case Search")),
    )

    registry = models.ForeignKey("DataRegistry", related_name="audit_logs", on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    domain = models.CharField(max_length=255)
    user = models.ForeignKey(User, related_name="registry_actions", on_delete=models.CASCADE)
    related_object_id = models.CharField(max_length=32)
    related_object_type = models.CharField(max_length=32, choices=RELATED_OBJECT_CHOICES)
    detail = JSONField(null=True)


class RegistryAuditHelper:
    def __init__(self, registry):
        self.registry = registry

    def registry_activated(self, user):
        self.log_registry_activated_deactivated(user, is_activated=True)

    def registry_deactivated(self, user):
        self.log_registry_activated_deactivated(user, is_activated=False)

    def invitation_accepted(self, user, invitation):
        return self.log_invitation_accepted_rejected(user, invitation, is_accepted=True)

    def invitation_rejected(self, user, invitation):
        return self.log_invitation_accepted_rejected(user, invitation, is_accepted=False)

    def invitation_added(self, user, invitation):
        return self.log_invitation_added_removed(user, invitation, is_added=True)

    def invitation_removed(self, user, invitation):
        return self.log_invitation_added_removed(user, invitation, is_added=False)

    def grant_added(self, user, grant):
        return self.log_grant_added_removed(user, grant, is_added=True)

    def grant_removed(self, user, grant):
        return self.log_grant_added_removed(user, grant, is_added=False)

    def schema_changed(self, user, new, old):
        return RegistryAuditLog.objects.create(
            registry=self.registry,
            user=user,
            action=RegistryAuditLog.ACTION_SCHEMA_CHANGED,
            domain=self.registry.domain,
            related_object_id=self.registry.id,
            related_object_type=RegistryAuditLog.RELATED_OBJECT_REGISTRY,
            detail={
                "new_schema": new,
                "old_schema": old,
            }
        )

    def data_accessed(self, user, domain, related_object, filters=None):
        if not related_object or not hasattr(related_object, "doc_type"):
            raise ValueError("Unexpected related object")

        if related_object.doc_type == "ReportConfiguration":
            related_object_id = related_object.get_id
            related_object_type = RegistryAuditLog.RELATED_OBJECT_UCR
        elif related_object.doc_type == "Application":
            related_object_id = related_object.get_id
            related_object_type = RegistryAuditLog.RELATED_OBJECT_APPLICATION
        else:
            raise ValueError(f"Unexpected related object type: {related_object.doc_type}")

        return RegistryAuditLog.objects.create(
            registry=self.registry,
            user=user,
            action=RegistryAuditLog.ACTION_DATA_ACCESSED,
            domain=domain,
            related_object_id=related_object_id,
            related_object_type=related_object_type,
            detail=filters
        )

    def log_registry_activated_deactivated(self, user, is_activated):
        return RegistryAuditLog.objects.create(
            registry=self.registry,
            user=user,
            action=RegistryAuditLog.ACTION_ACTIVATED if is_activated else RegistryAuditLog.ACTION_DEACTIVATED,
            domain=self.registry.domain,
            related_object_id=self.registry.id,
            related_object_type=RegistryAuditLog.RELATED_OBJECT_REGISTRY,
        )

    def log_invitation_added_removed(self, user, invitation, is_added):
        if is_added:
            action = RegistryAuditLog.ACTION_INVITATION_ADDED
        else:
            action = RegistryAuditLog.ACTION_INVITATION_REMOVED
        return RegistryAuditLog.objects.create(
            registry=self.registry,
            user=user,
            action=action,
            domain=invitation.domain,
            related_object_id=invitation.id,
            related_object_type=RegistryAuditLog.RELATED_OBJECT_INVITATION,
            detail={} if is_added else {"invitation_status": invitation.status}
        )

    def log_invitation_accepted_rejected(self, user, invitation, is_accepted):
        if is_accepted:
            action = RegistryAuditLog.ACTION_INVITATION_ACCEPTED
        else:
            action = RegistryAuditLog.ACTION_INVITATION_REJECTED
        return RegistryAuditLog.objects.create(
            registry=self.registry,
            user=user,
            action=action,
            domain=invitation.domain,
            related_object_id=invitation.id,
            related_object_type=RegistryAuditLog.RELATED_OBJECT_INVITATION,
        )

    def log_grant_added_removed(self, user, grant, is_added):
        RegistryAuditLog.objects.create(
            registry=self.registry,
            user=user,
            action=RegistryAuditLog.ACTION_GRANT_ADDED if is_added else RegistryAuditLog.ACTION_GRANT_REMOVED,
            domain=grant.domain,
            related_object_id=grant.id,
            related_object_type=RegistryAuditLog.RELATED_OBJECT_GRANT,
            detail={"to_domains": grant.to_domains}
        )
