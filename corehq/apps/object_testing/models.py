from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class ContextFactoryChoices(models.TextChoices):
    raw = 'raw', _("Raw JSON")


class ObjectTest(models.Model):
    domain = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    context_factory = models.CharField(max_length=32, choices=ContextFactoryChoices.choices)
    input = models.JSONField(default=dict)
    expected = models.JSONField(default=dict)
