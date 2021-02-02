from django.db import models
from django.utils.translation import ugettext as _
from jsonfield import JSONField

from dimagi.utils.couch import CriticalSection

PROPERTY_TYPE_CHOICES = (
    ('date', _('Date')),
    ('plain', _('Plain')),
    ('number', _('Number')),
    ('select', _('Select')),
    ('barcode', _('Barcode')),
    ('gps', _('GPS')),
    ('phone_number', _('Phone Number')),
    ('password', _('Password')),
    ('', 'No Type Currently Selected')
)


class CaseType(models.Model):
    domain = models.CharField(max_length=255, default=None)
    name = models.CharField(max_length=255, default=None)
    description = models.TextField(default='', blank=True)
    fully_generated = models.BooleanField(default=False)

    class Meta(object):
        unique_together = ('domain', 'name')

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

    def save(self, *args, **kwargs):
        from .util import get_data_dict_case_types
        get_data_dict_case_types.clear(self.domain)
        return super(CaseType, self).save(*args, **kwargs)


class CaseProperty(models.Model):
    case_type = models.ForeignKey(
        CaseType,
        on_delete=models.CASCADE,
        related_name='properties',
        related_query_name='property'
    )
    name = models.CharField(max_length=255, default=None)
    description = models.TextField(default='', blank=True)
    deprecated = models.BooleanField(default=False)
    data_type = models.CharField(
        choices=PROPERTY_TYPE_CHOICES,
        max_length=20,
        default='',
        blank=True
    )
    group = models.TextField(default='', blank=True)

    # option 1: "choices" property, could either go with a dict of choice ids to display names
    # or a list of structured data (e.g. {"value": "fever", "display": "patient has a fever"})
    # advantages: easy to implement. no joins necessary.
    # disadvantages: less structured data / validation. no reuse of choices
    choices = JSONField(default=dict)

    class Meta(object):
        unique_together = ('case_type', 'name')

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
                case_type_obj = CaseType.get_or_create(domain, case_type)
                prop = CaseProperty.objects.create(case_type=case_type_obj, name=name)
            return prop

    def save(self, *args, **kwargs):
        from .util import get_data_dict_props_by_case_type
        get_data_dict_props_by_case_type.clear(self.case_type.domain)
        return super(CaseProperty, self).save(*args, **kwargs)


# option 2: normalized list of "choices" mapping to properties.
# advantages: clearly structured in DB. easy to add more information to properties.
# disadvantages: lots of joins.
# note: could also make it a manytomany if we wanted to reuse property choices across properties
# though not convinced that's worth it.
class CasePropertyChoice(models.Model):
    case_property = models.ForeignKey(CaseProperty, on_delete=models.CASCADE)
    value = models.TextField()
    display = models.TextField()

    class Meta:
        unique_together = ('case_property', 'value')
