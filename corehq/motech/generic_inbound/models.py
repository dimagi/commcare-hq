from django.core.validators import validate_slug
from django.db import models

from memoized import memoized

from corehq.apps.userreports.models import UCRExpression
from corehq.apps.userreports.specs import FactoryContext
from corehq.motech.generic_inbound.utils import make_url_key


class ConfigurableAPI(models.Model):
    domain = models.CharField(max_length=255)
    key = models.CharField(max_length=32, validators=[validate_slug])
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, null=True)
    transform_expression = models.ForeignKey(UCRExpression, on_delete=models.PROTECT)

    class Meta:
        unique_together = ('domain', 'key')

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.key:
                raise Exception("'key' is auto-assigned")
            self.key = make_url_key()
        super().save(*args, **kwargs)

    @property
    @memoized
    def parsed_expression(self):
        return self.transform_expression.wrapped_definition(FactoryContext.empty())
