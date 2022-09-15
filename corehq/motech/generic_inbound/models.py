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
    transform_expression = models.ForeignKey(UCRExpression, on_delete=models.PROTECT)

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
