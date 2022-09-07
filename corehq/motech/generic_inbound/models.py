from django.core.exceptions import FieldError
from django.core.validators import validate_slug
from django.db import models

from memoized import memoized

from corehq.apps.userreports.models import UCRExpression
from corehq.apps.userreports.specs import FactoryContext
from corehq.motech.generic_inbound.utils import make_url_key
from corehq.util import reverse


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

    def __init__(self, *args, **kwargs):
        super(ConfigurableAPI, self).__init__(*args, **kwargs)
        # keep track to avoid refetching to check whether value is updated
        self.__original_key = self.key

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.key:
                raise FieldError("'key' is auto-assigned")
            self.key = make_url_key()
        elif self.key != self.__original_key:
            raise FieldError("'key' can not be changed")
        super().save(*args, **kwargs)

    @property
    @memoized
    def parsed_expression(self):
        return self.transform_expression.wrapped_definition(FactoryContext.empty())

    @property
    @memoized
    def absolute_url(self):
        return reverse("generic_inbound_api", args=[self.domain, self.key], absolute=True)
