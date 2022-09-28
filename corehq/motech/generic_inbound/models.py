from uuid import uuid4

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import FieldError
from django.core.validators import validate_slug
from django.db import models
from django.utils.translation import gettext_lazy as _

from field_audit import audit_fields
from field_audit.models import AuditingManager
from memoized import memoized

from corehq.apps.userreports.models import UCRExpression
from corehq.apps.userreports.specs import FactoryContext
from corehq.motech.generic_inbound.utils import make_url_key
from corehq.util import reverse


@audit_fields("domain", "url_key", "name", "transform_expression", audit_special_queryset_writes=True)
class ConfigurableAPI(models.Model):
    domain = models.CharField(max_length=255)
    url_key = models.CharField(max_length=32, validators=[validate_slug])
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    transform_expression = models.ForeignKey(UCRExpression, on_delete=models.PROTECT)

    objects = AuditingManager()

    class Meta:
        unique_together = ('domain', 'url_key')

    def __init__(self, *args, **kwargs):
        super(ConfigurableAPI, self).__init__(*args, **kwargs)
        # keep track to avoid refetching to check whether value is updated
        self.__original_url_key = self.url_key

    def __repr__(self):
        return f"ConfigurableAPI(domain='{self.domain}', name='{self.name}')"

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.url_key:
                raise FieldError("'url_key' is auto-assigned")
            self.url_key = make_url_key()
            self.__original_url_key = self.url_key
        elif self.url_key != self.__original_url_key:
            raise FieldError("'url_key' can not be changed")
        super().save(*args, **kwargs)

    @property
    @memoized
    def parsed_expression(self):
        return self.transform_expression.wrapped_definition(FactoryContext.empty())

    @property
    @memoized
    def absolute_url(self):
        return reverse("generic_inbound_api", args=[self.domain, self.url_key], absolute=True)


class ConfigurableApiValidation(models.Model):
    api = models.ForeignKey(ConfigurableAPI, on_delete=models.CASCADE, related_name="validations")
    name = models.CharField(max_length=64)
    expression = models.ForeignKey(UCRExpression, on_delete=models.PROTECT)
    message = models.TextField()

    def __repr__(self):
        return f"ConfigurableApiValidation(api={self.api}, name='{self.name}')"

    @property
    @memoized
    def parsed_expression(self):
        return self.expression.wrapped_definition(FactoryContext.empty())

    def to_json(self):
        return {
            "id": self.id,
            "api_id": self.api.id,
            "name": self.name,
            "expression_id": self.expression_id,
            "message": self.message,
        }


class RequestLog(models.Model):

    class Status(models.TextChoices):
        FILTERED = 'filtered', _('Filtered')
        VALIDATION_FAILED = 'validation_failed', _('Validation Failed')
        SUCCESS = 'success', _('Success')
        ERROR = 'error', _('Error')
        REVERTED = 'reverted', _('Reverted')

    class RequestMethod(models.TextChoices):
        POST = 'POST'
        PUT = 'PUT'
        PATCH = 'PATCH'

    id = models.UUIDField(primary_key=True, default=uuid4)
    domain = models.CharField(max_length=255)
    api = models.ForeignKey(ConfigurableAPI, on_delete=models.CASCADE)
    status = models.CharField(max_length=32, choices=Status.choices)

    timestamp = models.DateTimeField(auto_now=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=1)
    response_status = models.PositiveSmallIntegerField()
    error_message = models.TextField()

    username = models.CharField(max_length=128)
    request_method = models.CharField(max_length=32, choices=RequestMethod.choices)
    request_query = models.CharField(max_length=8192)
    request_body = models.TextField()
    request_headers = models.JSONField(default=dict)
    request_ip = models.GenericIPAddressField()

    class Meta:
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['status']),
            models.Index(fields=['username']),
        ]

    def __repr__(self):
        return f"RequestLog(domain='{self.domain}', api={self.api}, status='{self.status}')"


class ProcessingAttempt(models.Model):
    log = models.ForeignKey(RequestLog, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now=True, db_index=True)
    is_retry = models.BooleanField(default=False)
    response_status = models.PositiveSmallIntegerField(db_index=True)
    response_body = models.TextField()
    raw_response = models.JSONField(default=dict)

    xform_id = models.CharField(max_length=36, db_index=True, null=True, blank=True)
    case_ids = ArrayField(models.CharField(max_length=36), null=True, blank=True)

    def __repr__(self):
        return f"ProcessingAttempt(log={self.log}, response_status='{self.response_status}')"
