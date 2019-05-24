from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple

from dimagi.ext.couchdbkit import DocumentSchema

from corehq.motech.serializers import serializers
from corehq.motech.const import (
    COMMCARE_DATA_TYPES,
    DATA_TYPE_UNKNOWN,
    DIRECTIONS,
    # pylint: disable=unused-import,F401
    # (F401 = flake8 "'%s' imported but unused")
    # Used in ValueSource.check_direction doctest
    DIRECTION_IMPORT,
    DIRECTION_EXPORT,
    # pylint: enable=unused-import,F401
    DIRECTION_BOTH,
)
from dimagi.ext.couchdbkit import (
    DictProperty,
    StringProperty
)


CaseTriggerInfo = namedtuple('CaseTriggerInfo',
                             ['case_id', 'updates', 'created', 'closed', 'extra_fields', 'form_question_values'])


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
        return (
            self.doc_type == other.doc_type and
            self.external_data_type == other.external_data_type and
            self.commcare_data_type == other.commcare_data_type and
            self.direction == other.direction
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
    case_property = StringProperty()

    def _get_commcare_value(self, case_trigger_info):
        """
        Return the case property value from case updates, otherwise
        return it from extra_fields.

        extra_fields are current values of the case properties that have
        been included in an integration.

        >>> info = CaseTriggerInfo(
        ...     case_id='65e55473-e83b-4d78-9dde-eaf949758997',
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


def get_form_question_values(form_json):
    """
    Returns question-value pairs to result where questions are given as "/data/foo/bar"

    >>> values = get_form_question_values({'form': {'foo': {'bar': 'baz'}}})
    >>> values == {'/data/foo/bar': 'baz'}
    True

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
    _recurse_form_questions(form_json['form'], [b'/data'], result)  # "/data" is just convention, hopefully
    # familiar from form builder. The form's data will usually be immediately under "form_json['form']" but not
    # necessarily. If this causes problems we may need a more reliable way to get to it.

    metadata = {}
    if 'meta' in form_json['form']:
        if 'timeStart' in form_json['form']['meta']:
            metadata['timeStart'] = form_json['form']['meta']['timeStart']
        if 'timeEnd' in form_json['form']['meta']:
            metadata['timeEnd'] = form_json['form']['meta']['timeEnd']
    if 'received_on' in form_json:
        metadata['received_on'] = form_json['received_on']
    if metadata:
        _recurse_form_questions(metadata, [b'/metadata'], result)
    return result
