from datetime import datetime

from django.db import models
from django.utils.translation import gettext as _, gettext_lazy

from dimagi.utils.couch import CriticalSection
from dimagi.utils.parsing import ISO_DATE_FORMAT

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.app_schemas.case_properties import expire_case_properties_caches
from corehq.apps.case_importer import exceptions


class CaseType(models.Model):
    domain = models.CharField(max_length=255, default=None)
    name = models.CharField(max_length=255, default=None)
    description = models.TextField(default='', blank=True)
    fully_generated = models.BooleanField(default=False)
    is_deprecated = models.BooleanField(default=False)

    class Meta(object):
        unique_together = ('domain', 'name')

    def __str__(self):
        return self.name or super().__str__()

    @classmethod
    def get_or_create(cls, domain, case_type):
        key = 'data-dict-case-type-{domain}-{type}'.format(
            domain=domain, type=case_type
        )
        with CriticalSection([key]):
            try:
                case_type_obj = CaseType.objects.get(domain=domain, name=case_type)
            except CaseType.DoesNotExist:
                case_type_obj = CaseType.objects.create(domain=domain, name=case_type)
            return case_type_obj

    @classmethod
    def clear_cache(cls, domain):
        from .util import get_data_dict_case_types
        get_data_dict_case_types.clear(domain)

    def save(self, *args, **kwargs):
        self.clear_cache(self.domain)
        return super(CaseType, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.clear_cache(self.domain)
        return super(CaseType, self).delete(*args, **kwargs)


class CasePropertyGroup(models.Model):
    case_type = models.ForeignKey(
        CaseType,
        on_delete=models.CASCADE,
        related_name='groups',
        related_query_name='group'
    )
    name = models.CharField(max_length=255, default=None)
    description = models.TextField(default='', blank=True)
    index = models.IntegerField(default=0, blank=True)
    deprecated = models.BooleanField(default=False)

    class Meta(object):
        unique_together = ('case_type', 'name')

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('case_type', 'name'):
            return gettext_lazy('Group "{}" already exists for case type "{}"'.format(
                self.name, self.case_type.name
            ))
        else:
            return super().unique_error_message(model_class, unique_check)


class CaseProperty(models.Model):

    class DataType(models.TextChoices):
        DATE = 'date', _('Date')
        PLAIN = 'plain', _('Plain')
        NUMBER = 'number', _('Number')
        SELECT = 'select', _('Multiple Choice')
        BARCODE = 'barcode', _('Barcode')
        GPS = 'gps', _('GPS')
        PHONE_NUMBER = 'phone_number', _('Phone Number')
        PASSWORD = 'password', _('Password')
        UNDEFINED = '', _('No Type Currently Selected')

    case_type = models.ForeignKey(
        CaseType,
        on_delete=models.CASCADE,
        related_name='properties',
        related_query_name='property'
    )
    name = models.CharField(max_length=255, default=None)
    label = models.CharField(max_length=255, default='', blank=True)
    description = models.TextField(default='', blank=True)
    deprecated = models.BooleanField(default=False)
    data_type = models.CharField(
        choices=DataType.choices,
        max_length=20,
        default=DataType.UNDEFINED,
        blank=True,
    )
    index = models.IntegerField(default=0, blank=True)
    group = models.ForeignKey(
        CasePropertyGroup,
        on_delete=models.CASCADE,
        related_name='properties',
        related_query_name='property',
        db_column="group_id",
        null=True,
        blank=True
    )

    class Meta(object):
        unique_together = ('case_type', 'name')

    def __str__(self):
        if self.name and self.case_type.name:
            return f'{self.case_type.name}.{self.name}'
        return super().__str__()

    @classmethod
    def get_or_create(cls, name, case_type, domain):
        key = 'data-dict-property-{domain}-{type}-{name}'.format(
            domain=domain, type=case_type, name=name
        )
        with CriticalSection([key]):
            try:
                prop = CaseProperty.objects.get(
                    name=name, case_type__name=case_type, case_type__domain=domain
                )
            except CaseProperty.DoesNotExist:
                from corehq.apps.hqcase.case_helper import CaseCopier
                if name == CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME:
                    raise ValueError(f"{name} is a reserved property name")

                case_type_obj = CaseType.get_or_create(domain, case_type)
                prop = CaseProperty.objects.create(case_type=case_type_obj, name=name)
            return prop

    @classmethod
    def clear_caches(cls, domain, case_type):
        from .util import (
            get_data_dict_props_by_case_type,
            get_gps_properties,
        )
        get_data_dict_props_by_case_type.clear(domain)
        get_gps_properties.clear(domain, case_type)
        if domain_has_privilege(domain, privileges.DATA_DICTIONARY):
            expire_case_properties_caches(domain)

    def save(self, *args, **kwargs):
        self.clear_caches(self.case_type.domain, self.case_type.name)
        return super(CaseProperty, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.clear_caches(self.case_type.domain, self.case_type.name)
        return super(CaseProperty, self).delete(*args, **kwargs)

    def check_validity(self, value):
        if value and self.data_type == 'date':
            try:
                datetime.strptime(value, ISO_DATE_FORMAT)
            except ValueError:
                raise exceptions.InvalidDate(sample=value)
        elif value and self.data_type == 'select' and self.allowed_values.exists():
            if not self.allowed_values.filter(allowed_value=value).exists():
                raise exceptions.InvalidSelectValue(sample=value, message=self.valid_values_message)

    @property
    def valid_values_message(self):
        allowed_values = self.allowed_values.values_list('allowed_value', flat=True)
        allowed_string = ', '.join(f'"{av}"' for av in allowed_values)
        return _("Valid values: %s") % allowed_string

    @property
    def group_name(self):
        if self.group:
            return self.group.name


class CasePropertyAllowedValue(models.Model):
    case_property = models.ForeignKey(
        CaseProperty,
        on_delete=models.CASCADE,
        related_name='allowed_values',
        related_query_name='allowed_value'
    )
    allowed_value = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField(default='', blank=True)

    class Meta(object):
        unique_together = ('case_property', 'allowed_value')

    def __str__(self):
        return f'{self.case_property} valid value: "{self.allowed_value}"'
