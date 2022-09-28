from django.core.exceptions import FieldError
from django.core.validators import validate_slug
from django.db import models
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
    filter_expression = models.ForeignKey(
        UCRExpression, on_delete=models.PROTECT, related_name="api_filter", null=True, blank=True)
    transform_expression = models.ForeignKey(
        UCRExpression, on_delete=models.PROTECT, related_name="api_expression")

    objects = AuditingManager()

    class Meta:
        unique_together = ('domain', 'url_key')

    def __init__(self, *args, **kwargs):
        super(ConfigurableAPI, self).__init__(*args, **kwargs)
        # keep track to avoid refetching to check whether value is updated
        self.__original_url_key = self.url_key

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
    def parsed_filter(self):
        if not self.filter_expression:
            return None
        return self.filter_expression.wrapped_definition(FactoryContext.empty())

    @property
    @memoized
    def absolute_url(self):
        return reverse("generic_inbound_api", args=[self.domain, self.url_key], absolute=True)

    def get_validations(self):
        return list(self.validations.all())


class ConfigurableApiValidation(models.Model):
    api = models.ForeignKey(ConfigurableAPI, on_delete=models.CASCADE, related_name="validations")
    name = models.CharField(max_length=64)
    expression = models.ForeignKey(UCRExpression, on_delete=models.PROTECT)
    message = models.TextField()

    @property
    @memoized
    def parsed_expression(self):
        return self.expression.wrapped_definition(FactoryContext.empty())

    def get_error_context(self):
        return {
            "name": self.name,
            "message": self.message,
        }

    def to_json(self):
        return {
            "id": self.id,
            "api_id": self.api.id,
            "name": self.name,
            "expression_id": self.expression_id,
            "message": self.message,
        }
