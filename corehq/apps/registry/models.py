from datetime import datetime

from autoslug import AutoSlugField
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy

from corehq.apps.domain.utils import domain_name_stop_words


def slugify_remove_stops(text):
    words = slugify(text).split('-')
    stop_words = domain_name_stop_words()
    return "-".join([word for word in words if word not in stop_words])


class DataRegistry(models.Model):
    domain = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    # slug used for referencing the registry in app suite files, APIs etc.
    slug = AutoSlugField(populate_from='name', unique_with='domain', slugify=slugify_remove_stops)
    is_active = models.BooleanField(default=True)
    schema = JSONField(null=True)

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)


class RegistryInvitation(models.Model):
    registry = models.ForeignKey("DataRegistry", related_name="invitations", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    accepted_on = models.DateTimeField(null=True)
    accepted_by = models.ForeignKey(
        User, related_name="registry_accepted_invitations", on_delete=models.CASCADE, null=True
    )
    rejected_on = models.DateTimeField(null=True)
    rejected_by = models.ForeignKey(
        User, related_name="registry_rejected_invitations", on_delete=models.CASCADE, null=True
    )

    class Meta:
        unique_together = ("registry", "domain")


class RegistryGrant(models.Model):
    TYPE_ALLOW = "allow"
    TYPE_DENY = "deny"

    TYPE_CHOICES = [
        (TYPE_ALLOW, gettext_lazy("allow")),
        (TYPE_DENY, gettext_lazy("deny")),
    ]

    registry = models.ForeignKey("DataRegistry", related_name="grants", on_delete=models.CASCADE)
    from_domain = models.CharField(max_length=255)
    to_domains = ArrayField(models.CharField(max_length=255))
    type = models.CharField(max_length=8, choices=TYPE_CHOICES)


class RegistryPermission(models.Model):
    registry = models.ForeignKey("DataRegistry", related_name="permissions", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    read_only_group_id = models.CharField(max_length=255, null=True)

    class Meta:
        unique_together = ('registry', 'domain')
