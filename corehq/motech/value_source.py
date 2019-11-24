from typing import Any, Dict, Tuple, Optional

import attr
from jsonobject.containers import JsonDict
from jsonpath_rw import parse as parse_jsonpath
from schema import Optional as SchemaOptional
from schema import Or, Schema, SchemaError

from couchforms.const import TAG_FORM, TAG_META

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
    COMMCARE_DATA_TYPES_AND_UNKNOWN,
    DATA_TYPE_UNKNOWN,
    DIRECTION_BOTH,
    DIRECTION_EXPORT,
    DIRECTION_IMPORT,
    DIRECTIONS,
)
from corehq.motech.serializers import serializers


@attr.s
class CaseTriggerInfo:
    domain = attr.ib()
    case_id = attr.ib()
    type = attr.ib(default=None)
    name = attr.ib(default=None)
    owner_id = attr.ib(default=None)
    modified_by = attr.ib(default=None)
    updates = attr.ib(factory=dict)
    created = attr.ib(default=None)
    closed = attr.ib(default=None)
    extra_fields = attr.ib(factory=dict)
    form_question_values = attr.ib(factory=dict)

    def __str__(self):
        if self.name:
            return f'<CaseTriggerInfo {self.case_id} {self.name!r}>'
        return f"<CaseTriggerInfo {self.case_id}>"


def recurse_subclasses(cls):
    return (
        cls.__subclasses__() +
        [subsub for sub in cls.__subclasses__() for subsub in recurse_subclasses(sub)]
    )


@attr.s(auto_attribs=True, kw_only=True)
class ValueSource:
    """
    Subclasses model a reference to a value, like a case property or a
    form question.

    Use the `get_value()` method to fetch the value using the reference,
    and serialize it, if necessary, for the external system that it is
    being sent to.
    """
    external_data_type: Optional[str] = DATA_TYPE_UNKNOWN
    commcare_data_type: Optional[str] = DATA_TYPE_UNKNOWN
    # Whether the ValueSource is import-only ("in"), export-only ("out"), or
    # for both import and export (the default, None)
    direction: Optional[str] = DIRECTION_BOTH

    # Map CommCare values to remote system values or IDs. e.g.::
    #
    #     {
    #       "case_property": "pill"
    #       "value_map": {
    #         "red": "00ff0000",
    #         "blue": "000000ff",
    #       }
    #     }
    value_map: Optional[dict] = None

    # Used for importing a value from a JSON document.
    jsonpath: Optional[str] = None

    @classmethod
    def wrap(cls, data: dict):
        """
        Allows us to duck-type JsonObject, and useful for doing
        pre-instantiation transforms / dropping unwanted attributes.
        """
        data.pop("doc_type", None)
        return cls(**data)

    @classmethod
    def get_schema_params(cls) -> Tuple[Tuple, Dict]:
        args = ({
            SchemaOptional("doc_type"): str,
            SchemaOptional("external_data_type"): str,
            SchemaOptional("commcare_data_type"): Or(*COMMCARE_DATA_TYPES_AND_UNKNOWN),
            SchemaOptional("direction"): Or(*DIRECTIONS),
            SchemaOptional("value_map"): dict,
            SchemaOptional("jsonpath"): str,
        },)
        return args, {}

    @property
    def can_import(self):
        return not self.direction or self.direction == DIRECTION_IMPORT

    @property
    def can_export(self):
        return not self.direction or self.direction == DIRECTION_EXPORT

    def get_value(self, case_trigger_info: CaseTriggerInfo) -> Any:
        """
        Returns the value referred to by the ValueSource, serialized for
        the external system.
        """
        value = self.get_commcare_value(case_trigger_info)
        return self.serialize(value)

    def get_import_value(self, external_data):
        external_value = self.get_external_value(external_data)
        return self.deserialize(external_value)

    def get_commcare_value(self, case_trigger_info: CaseTriggerInfo) -> Any:
        raise NotImplementedError

    def get_external_value(self, external_data):
        if self.jsonpath:
            jsonpath = parse_jsonpath(self.jsonpath)
            matches = jsonpath.find(external_data)
            values = [m.value for m in matches]
            if not values:
                return None
            elif len(values) == 1:
                return values[0]
            else:
                return values

    def serialize(self, value: Any) -> Any:
        """
        Converts the value's CommCare data type or format to its data
        type or format for the external system, if necessary, otherwise
        returns the value unchanged.
        """
        if self.value_map:
            return self.value_map.get(value)
        serializer = (
            serializers.get((self.commcare_data_type, self.external_data_type))
            or serializers.get((None, self.external_data_type))
        )
        return serializer(value) if serializer else value

    def deserialize(self, external_value: Any) -> Any:
        """
        Converts the value's external data type or format to its data
        type or format for CommCare, if necessary, otherwise returns the
        value unchanged.
        """
        if self.value_map:
            reverse_map = {v: k for k, v in self.value_map.items()}
            return reverse_map.get(external_value)
        serializer = (
            serializers.get((self.external_data_type, self.commcare_data_type))
            or serializers.get((None, self.commcare_data_type))
        )
        return serializer(external_value) if serializer else external_value


@attr.s(auto_attribs=True, kw_only=True)
class CaseProperty(ValueSource):
    """
    A reference to a case property
    """
    # Example "person_property" value::
    #
    #     {
    #       "birthdate": {
    #         "case_property": "dob"
    #       }
    #     }
    #
    case_property: str

    class IsNotBlank:
        def validate(self, data):
            if isinstance(data, str) and len(data):
                return data
            raise SchemaError(f"Value cannot be blank.")

    @classmethod
    def get_schema_params(cls) -> Tuple[Tuple, Dict]:
        (schema, *other_args), kwargs = super().get_schema_params()
        schema.update({"case_property": cls.IsNotBlank()})
        return (schema, *other_args), kwargs

    def get_commcare_value(self, case_trigger_info: CaseTriggerInfo) -> Any:
        if self.case_property in case_trigger_info.updates:
            return case_trigger_info.updates[self.case_property]
        return case_trigger_info.extra_fields.get(self.case_property)


@attr.s(auto_attribs=True, kw_only=True)
class FormQuestion(ValueSource):
    """
    A reference to a form question
    """
    form_question: str

    @classmethod
    def get_schema_params(cls) -> Tuple[Tuple, Dict]:
        (schema, *other_args), kwargs = super().get_schema_params()
        schema.update({"form_question": str})
        return (schema, *other_args), kwargs

    def get_commcare_value(self, case_trigger_info: CaseTriggerInfo) -> Any:
        return case_trigger_info.form_question_values.get(
            self.form_question
        )


@attr.s(auto_attribs=True, kw_only=True)
class ConstantValue(ValueSource):
    """
    ConstantValue provides a ValueSource for constant values.

    ``value`` must be cast as ``value_data_type``.

    ``deserialize()`` returns the value for import. Use
    ``commcare_data_type`` to cast the import value.

    ``ConstantValue.get_value(case_trigger_info)`` returns the value for
    export.

    >>> one = ConstantValue.wrap({
    ...     "value": 1,
    ...     "value_data_type": COMMCARE_DATA_TYPE_INTEGER,
    ...     "commcare_data_type": COMMCARE_DATA_TYPE_DECIMAL,
    ...     "external_data_type": COMMCARE_DATA_TYPE_TEXT,
    ... })
    >>> info = CaseTriggerInfo("test-domain", None)
    >>> one.deserialize("foo")
    1.0
    >>> one.get_value(info)  # Returns '1.0', not '1'. See note below.
    '1.0'

    .. NOTE::
       ``one.get_value(info)`` returns  ``'1.0'``, not ``'1'``, because
       ``get_commcare_value()`` casts ``value`` as
       ``commcare_data_type`` first. ``serialize()`` casts it from
       ``commcare_data_type`` to ``external_data_type``.

       This may seem counter-intuitive, but we do it to preserve the
       behaviour of ``serialize()`` because it is public and is used
       outside the class.

    """
    value: str
    value_data_type: str = COMMCARE_DATA_TYPE_TEXT

    def __eq__(self, other):
        return (
            super().__eq__(other)
            and self.value == other.value
            and self.value_data_type == other.value_data_type
        )

    @classmethod
    def get_schema_params(cls) -> Tuple[Tuple, Dict]:
        (schema, *other_args), kwargs = super().get_schema_params()
        schema.update({
            "value": object,
            SchemaOptional("value_data_type"): str,
        })
        return (schema, *other_args), kwargs

    def get_commcare_value(self, case_trigger_info: CaseTriggerInfo) -> Any:
        serializer = (
            serializers.get((self.value_data_type, self.commcare_data_type))
            or serializers.get((None, self.commcare_data_type))
        )
        return serializer(self.value) if serializer else self.value

    def get_external_value(self, external_data):
        serializer = (
            serializers.get((self.value_data_type, self.external_data_type))
            or serializers.get((None, self.external_data_type))
        )
        return serializer(self.value) if serializer else self.value

    def deserialize(self, external_value: Any) -> Any:
        """
        Converts the value's external data type or format to its data
        type or format for CommCare, if necessary, otherwise returns the
        value unchanged.
        """
        serializer = (
            serializers.get((self.value_data_type, self.external_data_type))
            or serializers.get((None, self.external_data_type))
        )
        external_value = serializer(self.value) if serializer else self.value
        return super().deserialize(external_value)


@attr.s(auto_attribs=True, kw_only=True)
class CaseOwnerAncestorLocationField(ValueSource):
    """
    A reference to a location metadata value. The location may be the
    case owner, the case owner's location, or the first ancestor
    location of the case owner where the metadata value is set.
    """
    case_owner_ancestor_location_field: str

    @classmethod
    def wrap(cls, data):
        if "location_field" in data:
            data["case_owner_ancestor_location_field"] = data.pop("location_field")
        return super().wrap(data)

    @classmethod
    def get_schema_params(cls) -> Tuple[Tuple, Dict]:
        (schema, *other_args), kwargs = super().get_schema_params()
        schema.pop(SchemaOptional("doc_type"))
        old_style = schema.copy()
        old_style.update({
            "doc_type": "CaseOwnerAncestorLocationField",
            "location_field": str,
        })
        new_style = schema.copy()
        new_style.update({
            SchemaOptional("doc_type"): "CaseOwnerAncestorLocationField",
            "case_owner_ancestor_location_field": str,
        })
        schema = Or(old_style, new_style)
        return (schema, *other_args), kwargs

    def get_commcare_value(self, case_trigger_info: CaseTriggerInfo) -> Any:
        location = get_case_location(case_trigger_info)
        if location:
            return get_ancestor_location_metadata_value(
                location, self.case_owner_ancestor_location_field
            )


@attr.s(auto_attribs=True, kw_only=True)
class FormUserAncestorLocationField(ValueSource):
    """
    A reference to a location metadata value. The location is the form
    user's location, or the first ancestor location of the form user
    where the metadata value is set.
    """
    form_user_ancestor_location_field: str

    @classmethod
    def wrap(cls, data):
        if "location_field" in data:
            data["form_user_ancestor_location_field"] = data.pop("location_field")
        return super().wrap(data)

    @classmethod
    def get_schema_params(cls) -> Tuple[Tuple, Dict]:
        (schema, *other_args), kwargs = super().get_schema_params()
        schema.pop(SchemaOptional("doc_type"))
        old_style = schema.copy()
        old_style.update({
            "doc_type": "FormUserAncestorLocationField",
            "location_field": str,
        })
        new_style = schema.copy()
        new_style.update({
            SchemaOptional("doc_type"): "FormUserAncestorLocationField",
            "form_user_ancestor_location_field": str,
        })
        schema = Or(old_style, new_style)
        return (schema, *other_args), kwargs

    def get_commcare_value(self, case_trigger_info: CaseTriggerInfo) -> Any:
        user_id = case_trigger_info.form_question_values.get('/metadata/userID')
        location = get_owner_location(case_trigger_info.domain, user_id)
        if location:
            return get_ancestor_location_metadata_value(
                location, self.form_user_ancestor_location_field
            )


@attr.s
class CasePropertyConstantValue(ConstantValue, CaseProperty):
    pass


def as_value_source(data: dict) -> ValueSource:
    for subclass in recurse_subclasses(ValueSource):
        try:
            args, kwargs = subclass.get_schema_params()
            # .. WARNING::
            #    ``validate()`` can modify ``data``. This can break
            #    validation for other subclasses! If it is ever
            #    necessary to modify ``data``, it should be deep-copied
            #    (ouch) to preserve its state for the next iteration).
            valid_data = Schema(*args, **kwargs).validate(data)
        except SchemaError:
            pass
        else:
            return subclass.wrap(valid_data)
    else:
        raise TypeError(f"Unable to determine class for {data!r}")


def get_value(
    value_source_config: JsonDict,
    case_trigger_info: CaseTriggerInfo
) -> Any:
    """
    Returns the value referred to by the value source definition,
    serialized for the external system.
    """
    value_source = as_value_source(dict(value_source_config))
    return value_source.get_value(case_trigger_info)


def deserialize(value_source_config: JsonDict, external_value: Any) -> Any:
    """
    Converts the value's external data type or format to its data
    type or format for CommCare, if necessary, otherwise returns the
    value unchanged.
    """
    value_source = as_value_source(dict(value_source_config))
    return value_source.deserialize(external_value)


def get_form_question_values(form_json):
    """
    Given form JSON, returns question-value pairs, where questions are
    formatted "/data/foo/bar".

    e.g. Question "bar" in group "foo" has value "baz":

    >>> get_form_question_values({'form': {'foo': {'bar': 'baz'}}})
    {'/data/foo/bar': 'baz'}

    """
    _reserved_keys = ('@uiVersion', '@xmlns', '@name', '#type', 'case', 'meta', '@version')

    def _recurse_form_questions(form_dict, path, result_):
        for key, value in form_dict.items():
            if key in _reserved_keys:
                continue
            new_path = path + [key]
            if isinstance(value, list):
                # Repeat group
                for v in value:
                    assert isinstance(v, dict)
                    _recurse_form_questions(v, new_path, result_)
            elif isinstance(value, dict):
                # Group
                _recurse_form_questions(value, new_path, result_)
            else:
                # key is a question and value is its answer
                question = '/'.join((p.decode('utf8') if isinstance(p, bytes) else p for p in new_path))
                result_[question] = value

    result = {}
    _recurse_form_questions(form_json[TAG_FORM], [b'/data'], result)  # "/data" is just convention, hopefully
    # familiar from form builder. The form's data will usually be immediately under "form_json[TAG_FORM]" but not
    # necessarily. If this causes problems we may need a more reliable way to get to it.

    metadata = {}
    if 'meta' in form_json[TAG_FORM]:
        metadata.update(form_json[TAG_FORM][TAG_META])
    if 'received_on' in form_json:
        metadata['received_on'] = form_json['received_on']
    if metadata:
        _recurse_form_questions(metadata, [b'/metadata'], result)
    return result


def get_ancestor_location_metadata_value(location, metadata_key):
    assert isinstance(location, SQLLocation), type(location)
    for location in reversed(location.get_ancestors(include_self=True)):
        if location.metadata.get(metadata_key):
            return location.metadata[metadata_key]
    return None


def get_case_location(case):
    """
    If the owner of the case is a location, return it. Otherwise return
    the owner's primary location. If the case owner does not have a
    primary location, return None.
    """
    return get_owner_location(case.domain, get_owner_id(case))


def get_owner_location(domain, owner_id):
    owner = get_wrapped_owner(owner_id)
    if not owner:
        return None
    if isinstance(owner, SQLLocation):
        return owner
    location_id = owner.get_location_id(domain)
    return SQLLocation.by_location_id(location_id) if location_id else None
