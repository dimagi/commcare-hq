from importlib import import_module
from typing import List, Optional, Union

from django.db import models

import attr
from jsonfield import JSONField

from casexml.apps.case.models import CommCareCase

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.form_processor.models import CommCareCaseSQL
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.fhir.const import FHIR_VERSION_4_0_1, FHIR_VERSIONS
from corehq.motech.value_source import (
    CaseTriggerInfo,
    ValueSource,
    as_value_source,
)


@attr.s(auto_attribs=True)
class PropertyInfo:
    name: str
    json_name: str
    type_: type
    is_list: bool
    of_many: Optional[str]
    is_required: bool


class FHIRResourceType(models.Model):
    domain = models.CharField(max_length=127, db_index=True)
    fhir_version = models.CharField(max_length=12, choices=FHIR_VERSIONS,
                                    default=FHIR_VERSION_4_0_1)
    case_type = models.ForeignKey(CaseType, on_delete=models.CASCADE)

    # `fhirclient_class` values look like `module_name.ClassName`, and
    # can be imported from fhirclient.models.*module_name.ClassName*
    fhirclient_class = models.CharField(max_length=255)

    # `template` is used for defining a JSON document structure if it
    # cannot be built using only FHIRResourceAttributes
    template = JSONField(null=True, blank=True, default=None)

    def __str__(self):
        return self.fhirclient_class

    def get_fhirclient_class(self) -> type:
        """
        Returns a FHIR resource class from the fhirclient library.

        >>> resource_type = FHIRResourceType(
        ...     case_type=CaseType(name='contact'),
        ...     fhirclient_class='patient.PatientContact',
        ... )
        >>> class_type = resource_type.get_fhirclient_class()
        >>> class_type.__name__
        'PatientContact'

        """
        try:
            module_name, class_name = self.fhirclient_class.split('.')
            module = import_module(f'fhirclient.models.{module_name}')
            return getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as err:
            raise ConfigurationError('Unknown FHIR resource type '
                                     f'{self.fhirclient_class!r}') from err

    def get_properties_info(self) -> List[PropertyInfo]:
        """
        Returns a list of info about each resource property.

        >>> resource_type = FHIRResourceType(
        ...     case_type=CaseType(name='contact'),
        ...     fhirclient_class='patient.Patient',
        ... )
        >>> for pi in resource_type.get_properties_info():
        ...    if pi.of_many == 'multipleBirth':
        ...        print(pi.json_name, pi.type_)
        multipleBirthBoolean <class 'bool'>
        multipleBirthInteger <class 'int'>

        (For more information about how FHIR represents multiple births,
        see FHIR `Patient`_ documentation.)

        .. _Patient: https://www.hl7.org/fhir/patient.html

        """
        class_type = self.get_fhirclient_class()
        return [PropertyInfo(*p) for p in class_type().elementProperties()]


class FHIRResourceProperty(models.Model):
    resource_type = models.ForeignKey(FHIRResourceType,
                                      on_delete=models.CASCADE,
                                      related_name='properties')

    # `case_property`, `jsonpath` and `value_map` are set using the
    # Data Dictionary UI.
    case_property = models.ForeignKey(CaseProperty, on_delete=models.SET_NULL,
                                      null=True, blank=True, default=None)
    # Path to the FHIR resource property that corresponds with `case_property`
    jsonpath = models.TextField(null=True, blank=True, default=None)
    # Optional[dict] {CommCare value: FHIR value}
    value_map = JSONField(null=True, blank=True, default=None)

    # `value_source_config` is used when the Data Dictionary UI cannot
    # do what you need.
    value_source_config = JSONField(null=True, blank=True, default=None)

    def save(self, *args, **kwargs):
        if (
            self.case_property
            and self.case_property.case_type != self.resource_type.case_type
        ):
            raise ConfigurationError(
                "Invalid FHIRResourceProperty: case_property case type "
                f"'{self.case_property.case_type}' does not match "
                f"resource_type case type '{self.resource_type.case_type}'.")
        if (
            (self.case_property or self.jsonpath or self.value_map)
            and self.value_source_config
        ):
            raise ConfigurationError(
                "Invalid FHIRResourceProperty: Unable to set "
                "'value_source_config' when 'case_property', 'jsonpath' or "
                "'value_map' are set.")
        super().save(*args, **kwargs)

    @property
    def case_type(self) -> CaseType:
        return self.resource_type.case_type

    @property
    def case_property_name(self) -> Optional[str]:
        if self.case_property:
            return self.case_property.name
        if (
            self.value_source_config
            and 'case_property' in self.value_source_config
        ):
            return self.value_source_config['case_property']
        return None

    def get_value_source(self) -> ValueSource:
        """
        Returns a ValueSource for building FHIR resources.
        """
        if self.value_source_config:
            return as_value_source(self.value_source_config)

        if not (self.case_property and self.jsonpath):
            raise ConfigurationError(
                'Unable to set FHIR resource property value without case '
                'property and JSONPath.')
        value_source_config = {
            'case_property': self.case_property.name,
            'jsonpath': self.jsonpath,
        }
        if self.value_map:
            value_source_config['value_map'] = self.value_map
        return as_value_source(value_source_config)


def build_fhir_resource(case, version=FHIR_VERSION_4_0_1):
    case_type = CaseType.objects.get(
        domain=case.domain,
        name=case.type,
    )
    info = get_case_trigger_info(case, case_type)
    resource_type = (FHIRResourceType.objects
                     .prefetch_related('properties__case_property')
                     .get(case_type=case_type, fhir_version=version))
    fhir_resource = resource_type.template or {}
    for prop in resource_type.properties.all():
        value_source = prop.get_value_source()
        value_source.set_external_value(fhir_resource, info)
    return fhir_resource


def get_case_trigger_info(
        case: Union[CommCareCase, CommCareCaseSQL],
        case_type: CaseType,
) -> CaseTriggerInfo:
    """
    CaseTriggerInfo packages case (and form) data for use by ValueSource
    """
    prop_names = [p.name for p in case_type.properties.all()]
    return CaseTriggerInfo(
        domain=case.domain,
        case_id=case.case_id,
        type=case.type,
        updates={p: case.get_case_property(p) for p in prop_names},
    )
