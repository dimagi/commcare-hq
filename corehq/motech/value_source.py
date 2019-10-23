import attr
from couchdbkit import BadValueError
from jsonpath_rw import parse as parse_jsonpath

from couchforms.const import TAG_FORM, TAG_META
from dimagi.ext.couchdbkit import (
    DictProperty,
    DocumentSchema,
    Property,
    StringProperty,
)

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
    COMMCARE_DATA_TYPES,
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


def not_blank(value):
    if not str(value):
        raise BadValueError("Value cannot be blank.")


def recurse_subclasses(cls):
    return (
        cls.__subclasses__() +
        [subsub for sub in cls.__subclasses__() for subsub in recurse_subclasses(sub)]
    )


class ValueSource(DocumentSchema):
    """
    Subclasses model a reference to a value, like a case property or a
    form question.

    Use the `get_value()` method to fetch the value using the reference,
    and serialize it, if necessary, for the external system that it is
    being sent to.
    """
    external_data_type = StringProperty(required=False, default=DATA_TYPE_UNKNOWN, exclude_if_none=True)
    commcare_data_type = StringProperty(required=False, default=DATA_TYPE_UNKNOWN, exclude_if_none=True,
                                        choices=COMMCARE_DATA_TYPES + (DATA_TYPE_UNKNOWN,))
    # Whether the ValueSource is import-only ("in"), export-only ("out"), or
    # for both import and export (the default, None)
    direction = StringProperty(required=False, default=DIRECTION_BOTH, exclude_if_none=True,
                               choices=DIRECTIONS)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.doc_type == other.doc_type
            and self.external_data_type == other.external_data_type
            and self.commcare_data_type == other.commcare_data_type
            and self.direction == other.direction
        )

    @classmethod
    def wrap(cls, data):
        if cls is ValueSource:
            subclass = {
                sub._doc_type: sub for sub in recurse_subclasses(cls)
            }.get(data['doc_type'])
            return subclass.wrap(data) if subclass else None
        else:
            return super(ValueSource, cls).wrap(data)

    def serialize(self, value):
        """
        Converts the value's CommCare data type or format to its data
        type or format for the external system, if necessary, otherwise
        returns the value unchanged.
        """
        serializer = (serializers.get((self.commcare_data_type, self.external_data_type)) or
                      serializers.get((None, self.external_data_type)))
        return serializer(value) if serializer else value

    def deserialize(self, external_value):
        """
        Converts the value's external data type or format to its data
        type or format for CommCare, if necessary, otherwise returns the
        value unchanged.
        """
        serializer = (serializers.get((self.external_data_type, self.commcare_data_type)) or
                      serializers.get((None, self.commcare_data_type)))
        return serializer(external_value) if serializer else external_value

    def _get_commcare_value(self, case_trigger_info):
        raise NotImplementedError()

    def get_value(self, case_trigger_info):
        """
        Returns the value referred to by the ValueSource, serialized for
        the external system.
        """
        value = self._get_commcare_value(case_trigger_info)
        return self.serialize(value)

    def check_direction(self, direction):
        """
        Checks whether the ValueSource direction allows the value to be
        imported or exported.

        >>> value_source = ValueSource(direction=DIRECTION_BOTH)
        >>> value_source.check_direction(DIRECTION_EXPORT)
        True

        >>> value_source = ValueSource(direction=DIRECTION_IMPORT)
        >>> value_source.check_direction(DIRECTION_EXPORT)
        False

        """
        return not self.direction or direction == self.direction


class CaseProperty(ValueSource):
    """
    A reference to a case property
    """
    # Example "person_property" value::
    #
    #     {
    #       "birthdate": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "dob"
    #       }
    #     }
    #
    case_property = StringProperty(required=True, validators=not_blank)

    def _get_commcare_value(self, case_trigger_info):
        """
        Return the case property value from case updates, otherwise
        return it from extra_fields.

        extra_fields are current values of the case properties that have
        been included in an integration.

        >>> info = CaseTriggerInfo(
        ...     domain='test-domain',
        ...     case_id='65e55473-e83b-4d78-9dde-eaf949758997',
        ...     type='case',
        ...     name='',
        ...     owner_id='c0ffee',
        ...     modified_by='c0ffee',
        ...     updates={'foo': 1},
        ...     created=False,
        ...     closed=False,
        ...     extra_fields={'foo': 0, 'bar': 2},
        ...     form_question_values={},
        ... )
        >>> CaseProperty(case_property="foo")._get_commcare_value(info)
        1
        >>> CaseProperty(case_property="bar")._get_commcare_value(info)
        2
        >>> CaseProperty(case_property="baz")._get_commcare_value(info) is None
        True

        """
        if self.case_property in case_trigger_info.updates:
            return case_trigger_info.updates[self.case_property]
        return case_trigger_info.extra_fields.get(self.case_property)


class FormQuestion(ValueSource):
    """
    A reference to a form question
    """
    form_question = StringProperty()  # e.g. "/data/foo/bar"

    def _get_commcare_value(self, case_trigger_info):
        return case_trigger_info.form_question_values.get(self.form_question)


class ConstantString(ValueSource):
    """
    A constant value.

    Use the model's data types for the `serialize()` method to convert
    the value for the external system, if necessary.
    """
    # Example "person_property" value::
    #
    #     {
    #       "birthdate": {
    #         "doc_type": "ConstantString",
    #         "value": "Sep 7, 3761 BC"
    #       }
    #     }
    #
    value = StringProperty()

    def __eq__(self, other):
        return (
            super(ConstantString, self).__eq__(other) and
            self.value == other.value
        )

    def deserialize(self, external_value):
        # ConstantString doesn't have a corresponding case or form value
        return None

    def _get_commcare_value(self, case_trigger_info):
        return self.value


class ConstantValue(ConstantString):
    """
    ConstantValue provides a ValueSource for constant values.

    ``value`` must be cast as ``value_data_type``.

    ``ConstantValue.deserialize()`` returns the value for import. Use
    ``commcare_data_type`` to cast the import value.

    ``ConstantValue.get_value(case_trigger_info)`` returns the value for
    export.

    >>> one = ConstantValue.wrap({
    ...     "value": 1.0,
    ...     "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
    ...     "commcare_data_type": COMMCARE_DATA_TYPE_INTEGER,
    ...     "external_data_type": COMMCARE_DATA_TYPE_TEXT,
    ... })
    >>> info = CaseTriggerInfo("test-domain", None)
    >>> one.deserialize("foo")
    1
    >>> one.get_value(info)  # Returns '1', not '1.0'. See note below.
    '1'

    .. NOTE::
       ``one.get_value(info)`` returns  ``'1'``, not ``'1.0'``, because
       ``ConstantValue._get_commcare_value`` casts ``value`` as
       ``commcare_data_type`` first. ``ValueSource.serialize()`` casts
       it from ``commcare_data_type`` to ``external_data_type``.

       This may seem counter-intuitive, but we do it to preserve the
       behaviour of ``serialize()`` because it is public and is used
       outside the class.

    """
    value = Property()
    value_data_type = StringProperty(default=COMMCARE_DATA_TYPE_TEXT)

    def __eq__(self, other):
        return (
            super().__eq__(other)
            and self.value_data_type == other.value_data_type
        )

    def deserialize(self, external_value):
        """
        Ignores ``external_value`` and returns ``self.value`` cast from
        ``self.value_data_type`` to ``self.commcare_data_type``.
        """
        serializer = (serializers.get((self.value_data_type, self.commcare_data_type))
                      or serializers.get((None, self.commcare_data_type)))
        return serializer(self.value) if serializer else self.value

    def _get_commcare_value(self, case_trigger_info):
        """
        Returns ``self.value`` cast as ``self.commcare_data_type``.

        Used by ``self.get_value()``.
        """
        return self.deserialize(self.value)


class CasePropertyMap(CaseProperty):
    """
    Maps case property values to OpenMRS values or concept UUIDs
    """
    # Example "person_attribute" value::
    #
    #     {
    #       "00000000-771d-0000-0000-000000000000": {
    #         "doc_type": "CasePropertyMap",
    #         "case_property": "pill"
    #         "value_map": {
    #           "red": "00ff0000-771d-0000-0000-000000000000",
    #           "blue": "000000ff-771d-0000-0000-000000000000",
    #         }
    #       }
    #     }
    #
    value_map = DictProperty()

    def serialize(self, value):
        # Don't bother serializing. self.value_map does that already.
        #
        # Using `.get()` because it's OK if some CommCare answers are
        # not mapped to OpenMRS concepts, e.g. when only the "yes" value
        # of a yes-no question in CommCare is mapped to a concept in
        # OpenMRS.
        return self.value_map.get(value)

    def deserialize(self, external_value):
        reverse_map = {v: k for k, v in self.value_map.items()}
        return reverse_map.get(external_value)


class FormQuestionMap(FormQuestion):
    """
    Maps form question values to OpenMRS values or concept UUIDs
    """
    value_map = DictProperty()

    def serialize(self, value):
        return self.value_map.get(value)

    def deserialize(self, external_value):
        reverse_map = {v: k for k, v in self.value_map.items()}
        return reverse_map.get(external_value)


class CaseOwnerAncestorLocationField(ValueSource):
    """
    A reference to a location metadata value. The location may be the
    case owner, the case owner's location, or the first ancestor
    location of the case owner where the metadata value is set.
    """
    location_field = StringProperty()

    def _get_commcare_value(self, case_trigger_info):
        location = get_case_location(case_trigger_info)
        if location:
            return get_ancestor_location_metadata_value(location, self.location_field)


class FormUserAncestorLocationField(ValueSource):
    """
    A reference to a location metadata value. The location is the form
    user's location, or the first ancestor location of the form user
    where the metadata value is set.
    """
    location_field = StringProperty()

    def _get_commcare_value(self, case_trigger_info):
        user_id = case_trigger_info.form_question_values.get('/metadata/userID')
        location = get_owner_location(case_trigger_info.domain, user_id)
        if location:
            return get_ancestor_location_metadata_value(location, self.location_field)


class CasePropertyJsonPath(CaseProperty):
    """
    Used for importing a value from a JSON document.
    """
    jsonpath_str = StringProperty(required=True, validators=not_blank)

    def get_external_value(self, json_doc):
        jsonpath = parse_jsonpath(self.jsonpath_str)
        matches = jsonpath.find(json_doc)
        values = [m.value for m in matches]
        if not values:
            return None
        elif len(values) == 1:
            return values[0]
        else:
            return values


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
