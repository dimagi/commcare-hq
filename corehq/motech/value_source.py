from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple

from couchdbkit.ext.django.schema import DocumentSchema

from corehq.motech.serializers import serializers
from corehq.motech.const import DATA_TYPE_UNKNOWN, COMMCARE_DATA_TYPES
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
    external_data_type = StringProperty(required=False, default=DATA_TYPE_UNKNOWN)
    commcare_data_type = StringProperty(required=False, default=DATA_TYPE_UNKNOWN,
                                        choices=COMMCARE_DATA_TYPES + (DATA_TYPE_UNKNOWN,))

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
        serializer = (serializers.get((self.commcare_data_type, self.external_data_type)) or
                      serializers.get((None, self.external_data_type)))
        return serializer(value) if serializer else value

    def deserialize(self, external_value):
        serializer = (serializers.get((self.external_data_type, self.commcare_data_type)) or
                      serializers.get((None, self.commcare_data_type)))
        return serializer(external_value) if serializer else external_value

    def get_commcare_value(self, case_trigger_info):
        raise NotImplementedError()

    def get_value(self, case_trigger_info):
        value = self.get_commcare_value(case_trigger_info)
        return self.serialize(value)


class CaseProperty(ValueSource):
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

    def get_commcare_value(self, case_trigger_info):
        return case_trigger_info.updates.get(self.case_property)


class FormQuestion(ValueSource):
    form_question = StringProperty()  # e.g. "/data/foo/bar"

    def get_commcare_value(self, case_trigger_info):
        return case_trigger_info.form_question_values.get(self.form_question)


class ConstantString(ValueSource):
    # Example "person_property" value::
    #
    #     {
    #       "birthdate": {
    #         "doc_type": "ConstantString",
    #         "value": "Sep 7, 3761 BC"
    #       }
    #     }
    #
    # Serializes value to convert dates, etc. to a format that is
    # acceptable to whatever API we are sending it to.
    value = StringProperty()

    def deserialize(self, external_value):
        # ConstantString doesn't have a corresponding case or form value
        return None

    def get_commcare_value(self, case_trigger_info):
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
    return result
