import json
import os
from typing import Optional

from django.conf import settings
from django.db import models

from jsonfield import JSONField

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.fhir.const import FHIR_VERSION_4_0_1, FHIR_VERSIONS
from corehq.motech.value_source import ValueSource, as_value_source


class FHIRResourceType(models.Model):
    domain = models.CharField(max_length=127, db_index=True)
    fhir_version = models.CharField(max_length=12, choices=FHIR_VERSIONS,
                                    default=FHIR_VERSION_4_0_1)
    case_type = models.ForeignKey(CaseType, on_delete=models.CASCADE)

    # For a list of resource types, see http://hl7.org/fhir/resourcelist.html
    name = models.CharField(max_length=255)

    # `template` offers a way to define a FHIR resource if it cannot be
    # built using only mapped case properties.
    template = JSONField(null=True, blank=True, default=None)

    def __str__(self):
        return self.name

    def get_json_schema(self) -> dict:
        """
        Returns the JSON schema of this resource type.

        >>> resource_type = FHIRResourceType(
        ...     case_type=CaseType(name='mother'),
        ...     name='Patient',
        ... )
        >>> schema = resource_type.get_json_schema()
        >>> schema['$ref']
        '#/definitions/Patient'

        """
        ver = dict(FHIR_VERSIONS)[self.fhir_version].lower()
        schema_file = f'{self.name}.schema.json'
        path = os.path.join(settings.BASE_DIR, 'corehq', 'motech', 'fhir',
                            'json-schema', ver, schema_file)
        try:
            with open(path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            raise ConfigurationError(
                f'Unknown resource type {self.name!r} for FHIR version '
                f'{self.fhir_version}'
            )

    @classmethod
    def get_names(cls, version=FHIR_VERSION_4_0_1):
        ver = dict(FHIR_VERSIONS)[version].lower()
        path = os.path.join(settings.BASE_DIR, 'corehq', 'motech', 'fhir',
                            'json-schema', ver)
        ext = len('.schema.json')
        return [n[:-ext] for n in os.listdir(path)]


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

        e.g. You could build a FHIR resource as follows::

            def build_fhir_resource(case, version=FHIR_VERSION_4_0_1):
                case_type = CaseType.objects.get(
                    domain=case.domain,
                    name=case.type,
                )
                resource_type = FHIRResourceType.objects.get(
                    case_type=case_type,
                    fhir_version=version,
                )

                # CaseTriggerInfo packages data for use by ValueSource
                prop_names = [p.name for p in case_type.properties]
                info = CaseTriggerInfo(
                    domain=domain,
                    case_id=case.case_id,
                    case_type=case.type,
                    updates={p: case.get_case_property(p) for p in prop_names},
                )

                fhir_resource = resource_type.template or {}
                for property in resource_type.properties:
                    value_source = property.get_value_source()
                    value_source.set_external_value(fhir_resource, info)
                return fhir_resource

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
