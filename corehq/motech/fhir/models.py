"""
FHIR Models
===========

FHIRResourceType maps a CommCare case type to a FHIR resource type. It
is used by FHIRRepeater and the FHIR API for building a FHIR resource
from case properties and other sources of data.

FHIRResourceProperty determines how to set the value of a property of a
FHIR resource. FHIRResourceType has many FHIRResourceProperty instances.

For more information, see
:doc:`the CommCare FHIR Integration docs <docs/index>`.

Importing FHIR data involves more models. The primary one is
FHIRImportResourceType. It serves the same purpose as FHIRResourceType,
but for incoming data.

FHIRImportResourceProperty determines how to import the value of a FHIR
resource property.

ResourceTypeRelationship tracks how to import related resources.

FHIRImportConfig stores information about the remote FHIR API.

For more information, see :doc:`docs/fhir_import_config`.

"""
import json
import os
from typing import Optional, Union

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from couchdbkit import ResourceNotFound
from jsonfield import JSONField
from jsonschema import RefResolver
from jsonschema import ValidationError as JSONValidationError
from jsonschema import validate

from casexml.apps.case.models import CommCareCase

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.export.const import KNOWN_CASE_PROPERTIES
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.form_processor.models import CommCareCaseSQL
from corehq.motech.const import (
    IMPORT_FREQUENCY_CHOICES,
    IMPORT_FREQUENCY_DAILY,
)
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.models import ConnectionSettings
from corehq.motech.value_source import (
    CaseTriggerInfo,
    ValueSource,
    as_value_source,
)

from .const import (
    FHIR_VERSION_4_0_1,
    FHIR_VERSIONS,
    OWNER_TYPE_CHOICES,
    OWNER_TYPE_GROUP,
    OWNER_TYPE_LOCATION,
    OWNER_TYPE_USER,
)
from .validators import validate_supported_type


class FHIRResourceType(models.Model):
    domain = models.CharField(max_length=127, db_index=True)
    fhir_version = models.CharField(max_length=12, choices=FHIR_VERSIONS,
                                    default=FHIR_VERSION_4_0_1)
    case_type = models.ForeignKey(CaseType, on_delete=models.CASCADE)

    # For a list of resource types, see http://hl7.org/fhir/resourcelist.html
    name = models.CharField(max_length=255, validators=[validate_supported_type])

    class Meta:
        unique_together = ('case_type', 'fhir_version')

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
        try:
            with open(self._schema_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            raise ConfigurationError(
                f'Unknown resource type {self.name!r} for FHIR version '
                f'{self.fhir_version}'
            )

    @classmethod
    def get_names(cls, version=FHIR_VERSION_4_0_1):
        schema_dir = get_schema_dir(version)
        ext = len('.schema.json')
        return [n[:-ext] for n in os.listdir(schema_dir)]

    def validate_resource(self, fhir_resource):
        schema = self.get_json_schema()
        resolver = RefResolver(base_uri=f'file://{self._schema_file}',
                               referrer=schema)
        try:
            validate(fhir_resource, schema, resolver=resolver)
        except JSONValidationError as err:
            raise ConfigurationError(
                f'Validation failed for resource {fhir_resource!r}: {err}'
            ) from err

    @property
    def _schema_file(self):
        return os.path.join(self._schema_dir, f'{self.name}.schema.json')

    @property
    def _schema_dir(self):
        return get_schema_dir(self.fhir_version)


def get_schema_dir(version):
    ver = dict(FHIR_VERSIONS)[version].lower()
    return os.path.join(settings.BASE_DIR, 'corehq', 'motech', 'fhir',
                        'json-schema', ver)


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

    def __str__(self):
        jsonpath = self.value_source_jsonpath
        if jsonpath.startswith('$.'):
            jsonpath = jsonpath[2:]
        return f'{self.resource_type.name}.{jsonpath}'

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
    def value_source_jsonpath(self) -> str:
        if self.jsonpath:
            return self.jsonpath
        if 'jsonpath' in self.value_source_config:
            return self.value_source_config['jsonpath']
        return ''

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


def build_fhir_resource(
    case: Union[CommCareCase, CommCareCaseSQL],
    fhir_version: str = FHIR_VERSION_4_0_1,
) -> Optional[dict]:
    """
    Builds a FHIR resource using data from ``case``. Returns ``None`` if
    mappings do not exist.

    Used by the FHIR API.
    """
    resource_type = get_resource_type_or_none(case, fhir_version)
    if resource_type is None:
        return None
    info = get_case_trigger_info(case, resource_type)
    return _build_fhir_resource(info, resource_type)


def build_fhir_resource_for_info(
    info: CaseTriggerInfo,
    resource_type: FHIRResourceType,
) -> Optional[dict]:
    """
    Builds a FHIR resource using data from ``info``. Returns ``None`` if
    mappings do not exist, or if there is no data to forward.

    Used by ``FHIRRepeater``.
    """
    return _build_fhir_resource(info, resource_type, skip_empty=True)


def _build_fhir_resource(
    info: CaseTriggerInfo,
    resource_type: FHIRResourceType,
    *,
    skip_empty: bool = False,
) -> Optional[dict]:

    fhir_resource = {}
    for prop in resource_type.properties.all():
        value_source = prop.get_value_source()
        value_source.set_external_value(fhir_resource, info)
    if not fhir_resource and skip_empty:
        return None

    fhir_resource.update({
        'id': info.case_id,
        'resourceType': resource_type.name,  # Always required
    })
    resource_type.validate_resource(fhir_resource)
    return fhir_resource


def get_case_trigger_info(
    case: Union[CommCareCase, CommCareCaseSQL],
    resource_type: FHIRResourceType,
    case_block: Optional[dict] = None,
    form_question_values: Optional[dict] = None,
) -> CaseTriggerInfo:
    """
    Returns ``CaseTriggerInfo`` instance for ``case``.

    Ignores case properties that aren't in the Data Dictionary.

    ``CaseTriggerInfo`` packages case (and form) data for use by
    ``ValueSource``.
    """
    if case_block is None:
        case_block = {}
    else:
        assert case_block['@case_id'] == case.case_id
    if form_question_values is None:
        form_question_values = {}

    case_create = case_block.get('create') or {}
    case_update = case_block.get('update') or {}
    case_property_names = _get_case_property_names(resource_type)
    extra_fields = {
        # CouchDB (via jsonobject) casts case properties as `Decimal`,
        # `date`, `time` and `datetime` but SQL stores them as `str`.
        p: _str_or_none(case.get_case_property(p))  # Standardize.
        for p in case_property_names
    }
    return CaseTriggerInfo(
        domain=case.domain,
        case_id=case.case_id,
        type=case.type,
        name=case.name,
        owner_id=case.owner_id,
        modified_by=case.modified_by,
        updates={**case_create, **case_update},
        created='create' in case_block if case_block else None,
        closed='close' in case_block if case_block else None,
        extra_fields=extra_fields,
        form_question_values=form_question_values,
    )


def _get_case_property_names(resource_type):
    """
    Returns the names of mapped case properties, plus "external_id"
    """
    # We will need "external_id" to tell whether a case already exists
    # on the remote service.
    case_property_names = ['external_id']
    for resource_property in resource_type.properties.all():
        value_source = resource_property.get_value_source()
        if hasattr(value_source, 'case_property'):
            case_property_names.append(value_source.case_property)
    return case_property_names


def _str_or_none(value):
    return None if value is None else str(value)


def get_resource_type_or_none(case, fhir_version) -> Optional[FHIRResourceType]:
    try:
        return (
            FHIRResourceType.objects
            .select_related('case_type')
            .prefetch_related('properties__case_property')
            .get(
                domain=case.domain,
                case_type__name=case.type,
                fhir_version=fhir_version,
            )
        )
    except FHIRResourceType.DoesNotExist:
        return None


class FHIRImportConfig(models.Model):
    domain = models.CharField(max_length=127)
    connection_settings = models.ForeignKey(
        ConnectionSettings,
        on_delete=models.PROTECT,
    )
    fhir_version = models.CharField(
        max_length=12,
        choices=FHIR_VERSIONS,
        default=FHIR_VERSION_4_0_1,
    )
    frequency = models.CharField(
        max_length=12,
        choices=IMPORT_FREQUENCY_CHOICES,
        default=IMPORT_FREQUENCY_DAILY,
    )
    # ID of group, location or user that will own imported cases
    owner_id = models.CharField(max_length=36, null=False, blank=False)
    owner_type = models.CharField(max_length=12, choices=OWNER_TYPE_CHOICES)

    class Meta:
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['frequency']),
        ]

    def __str__(self):
        return f'{self.connection_settings} ({self.frequency})'

    def clean(self):
        super().clean()
        try:
            self.get_owner()
        except ConfigurationError as err:
            raise DjangoValidationError(str(err)) from err

    def get_owner(self):
        if not self.owner_id:
            raise ConfigurationError('Owner ID missing')
        try:
            if self.owner_type == OWNER_TYPE_GROUP:
                return Group.get(self.owner_id)
            elif self.owner_type == OWNER_TYPE_LOCATION:
                return SQLLocation.objects.get(location_id=self.owner_id)
            elif self.owner_type == OWNER_TYPE_USER:
                user = CouchUser.get_by_user_id(self.owner_id)
                if user:
                    return user
                else:
                    raise ResourceNotFound()
            else:
                raise ConfigurationError(f'Unknown owner type {self.owner_type!r}')
        except (ResourceNotFound, SQLLocation.DoesNotExist):
            raise ConfigurationError(f'{self.owner_type.capitalize()} '
                                     f'{self.owner_id!r} does not exist')


class FHIRImportResourceType(models.Model):
    """
    Similar to ``FHIRResourceType`` but allows importing different case
    types, with different mappings, from those used by ``FHIRRepeater``
    and the FHIR API.

    ``import_related_only`` determines whether the ``FHIRImportConfig``
    searches the remote service for instances, or only imports instances
    related to the resource types it is interested in. e.g. Only import
    the Patients of imported ServiceRequests, not all Patients. Or only
    import the Person resources who are the contacts of imported
    Patients, not all Person resources.

    If ``import_related_only`` is ``False`` (the default) , then
    ``FHIRImportResourceType`` imports resources filtered by the
    ``search_params`` field.

    .. note::

       If ``import_related_only`` is ``False`` and ``search_params`` is
       empty, then all resources of that type will be imported.

    See the ``jsonpath_to_related_resource_type`` related name defined
    in ``ResourceTypeRelationship`` for details of how related resource
    types are set.
    """
    import_config = models.ForeignKey(
        FHIRImportConfig,
        on_delete=models.CASCADE,
        related_name='resource_types',
    )
    name = models.CharField(max_length=255)
    case_type = models.ForeignKey(CaseType, on_delete=models.CASCADE)

    import_related_only = models.BooleanField(default=False)
    search_params = JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name

    @property
    def domain(self):
        return self.import_config.domain

    def iter_case_property_value_sources(self):
        name_properties = {"name", "case_name"}
        readonly = set(KNOWN_CASE_PROPERTIES) - name_properties | {'case_id'}
        for prop in self.properties.all():
            if 'case_property' in prop.value_source_config:
                case_property = prop.value_source_config['case_property']
                if case_property in readonly:
                    continue
                yield prop.get_value_source()


class ResourceTypeRelationship(models.Model):
    """
    ``ResourceTypeRelationship`` maps a ``FHIRImportResourceType`` to a
    related ``FHIRImportResourceType`` by the JSONPath of a property.
    e.g. Consider the following ServiceRequest:

    .. code-block:: javascript

        {
            "id": "67890",
            "resourceType": "ServiceRequest",
            "subject": {
                "reference": "Patient/12345",
                "display": "Alice Apple"
            },
            "status": "active",
            "intent": "directive",
            "priority": "routine"
        }

    This ServiceRequest can be linked to its Patient as follows:

    .. code-block:: python

        service_request = FHIRImportResourceType(
            name='ServiceRequest',
            search_params={'status': 'active'},
        )
        patient = FHIRImportResourceType(
            name='Patient',
            import_related_only=True,
        )
        service_request_patient = ResourceTypeRelationship(
            resource_type=service_request,
            jsonpath='$.subject.reference',
            related_resource_type=patient,
        )

    ``jsonpath`` is the JSONPath for the reference to the related
    resource. e.g. The JSONPath for the reference to the Patient of a
    ServiceRequest is "$.subject.reference". Its value might look like
    "Patient/12345".
    """
    resource_type = models.ForeignKey(
        FHIRImportResourceType,
        on_delete=models.CASCADE,
        related_name='jsonpaths_to_related_resource_types',
    )

    # JSONPath for the reference to the resource of ``related_resource_type``
    jsonpath = models.TextField(default='')

    # Related resource type to import
    related_resource_type = models.ForeignKey(
        FHIRImportResourceType,
        on_delete=models.CASCADE,
    )

    # Create index on child case to imported parent case?
    related_resource_is_parent = models.BooleanField(default=False)

    def __str__(self):
        jsonpath = self.jsonpath
        if jsonpath.startswith('$.'):
            jsonpath = jsonpath[2:]
        return (f'{self.resource_type.name}.{jsonpath} → '
                f'{self.related_resource_type.name}')


class FHIRImportResourceProperty(models.Model):
    resource_type = models.ForeignKey(
        FHIRImportResourceType,
        on_delete=models.CASCADE,
        related_name='properties',
    )
    value_source_config: dict = JSONField(default=dict)

    def __str__(self):
        jsonpath = self.value_source_jsonpath
        if jsonpath.startswith('$.'):
            jsonpath = jsonpath[2:]
        return f'{self.resource_type.name}.{jsonpath}'

    @property
    def case_type(self) -> CaseType:
        return self.resource_type.case_type

    @property
    def value_source_jsonpath(self) -> str:
        return self.value_source_config.get('jsonpath', '')

    def get_value_source(self) -> ValueSource:
        return as_value_source(self.value_source_config)

    def save(self, *args, **kwargs):
        try:
            self.get_value_source()
        except TypeError as err:
            raise ConfigurationError from err
        super().save(*args, **kwargs)
