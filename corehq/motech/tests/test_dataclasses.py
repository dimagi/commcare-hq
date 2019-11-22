from functools import singledispatch
from typing import Optional, Any

from dataclasses import dataclass, asdict

from dimagi.ext.couchdbkit import Document, DictProperty
from django.test import SimpleTestCase
from schema import Schema, Optional as SchemaOptional, Or

from corehq.motech.const import (
    COMMCARE_DATA_TYPE_TEXT,
    COMMCARE_DATA_TYPES,
    DATA_TYPE_UNKNOWN,
    DIRECTION_BOTH,
    DIRECTIONS,
)
from corehq.motech.serializers import serializers
from corehq.motech.value_source import (
    CaseTriggerInfo,
    recurse_subclasses,
)

DOMAIN = "test-domain"


# The following shows how one could use dataclasses (Python 3.7,
# backported to Python 3.6 with the *dataclasses* library) as an
# alternative to JsonObject. This has been interesting to explore, but
# I don't think the benefit would outweigh the effort of migrating
# MOTECH configurations to it, and the confusion of introducing an
# alternative to couchdbkit/JsonObject now.

# (It is intended to bring the features of *attrs* into the standard
# library though.)

# The ``get_schema_dict()`` method offers a way to cast a dict as a
# ValueSource subclass. See the ``asdataclass()`` function below. This
# approach is not specifically for dataclasses; it would work with
# JsonObject classes too, without needing ``doc_type`` to work out what
# subclass an instance is.

@dataclass
class ValueSource:
    external_data_type: Optional[str] = DATA_TYPE_UNKNOWN
    commcare_data_type: Optional[str] = DATA_TYPE_UNKNOWN
    direction: Optional[str] = DIRECTION_BOTH
    value_map: Optional[dict] = None
    jsonpath: Optional[str] = None

    @classmethod
    def get_schema_dict(cls) -> dict:
        return {
            SchemaOptional("external_data_type"): str,
            SchemaOptional("commcare_data_type"): Or(
                COMMCARE_DATA_TYPES + (DATA_TYPE_UNKNOWN,)),
            SchemaOptional("direction"): Or(DIRECTIONS),
            SchemaOptional("value_map"): dict,
            SchemaOptional("jsonpath"): str,
        }


@dataclass
class CaseProperty(ValueSource):
    # ``case_property`` requires a default value because
    # ``CaseProperty``'s superclass ``ValueSource`` has default values,
    # and dataclasses add attributes of subclasses after the attributes
    # of superclasses.
    # A Falsey default value allows us to validate in __post_init__()
    case_property: str = ""

    def __post_init__(self):
        if not self.case_property:
            raise ValueError("case_property requires a value.")

    @classmethod
    def get_schema_dict(cls) -> dict:
        schema = super().get_schema_dict().copy()
        schema.update({"case_property": str})
        return schema


@dataclass
class FormQuestion(ValueSource):
    form_question: str = ""

    def __post_init__(self):
        if not self.form_question:
            raise ValueError("form_question requires a value.")

    @classmethod
    def get_schema_dict(cls) -> dict:
        schema = super().get_schema_dict().copy()
        schema.update({"form_question": str})
        return schema


@dataclass
class ConstantValue(ValueSource):
    value: Any = ""
    value_data_type: str = COMMCARE_DATA_TYPE_TEXT

    @classmethod
    def get_schema_dict(cls) -> dict:
        schema = super().get_schema_dict().copy()
        schema.update({
            "value": object,
            SchemaOptional("value_data_type"): str,
        })
        return schema


def asdataclass(data):
    for dataclass in recurse_subclasses(ValueSource):
        if Schema(dataclass.get_schema_dict()).is_valid(data):
            return dataclass(**data)
    else:
        raise TypeError(f"Unable to determine dataclass for {data!r}")


class SpamDoc(Document):
    spam = DictProperty()


class DictPropertyTests(SimpleTestCase):

    def test_setting_property(self):
        case_property = CaseProperty(case_property="spam")
        spam_doc = SpamDoc.wrap({
            "spam": asdict(case_property)
        })
        spam_doc.validate()

    def test_asdataclass_case_property(self):
        spam_doc = SpamDoc.wrap({
            "spam": {"case_property": "spam"}
        })
        dict_not_jsondict = dict(spam_doc.spam)
        case_property = asdataclass(dict_not_jsondict)
        self.assertIsInstance(case_property, CaseProperty)

    def test_asdataclass_form_question(self):
        spam_doc = SpamDoc.wrap({
            "spam": {"form_question": "/data/spam"}
        })
        form_question = asdataclass(dict(spam_doc.spam))
        self.assertIsInstance(form_question, FormQuestion)

    def test_asdataclass_constant_value(self):
        spam_doc = SpamDoc.wrap({
            "spam": {"value": "spam"}
        })
        case_property = asdataclass(dict(spam_doc.spam))
        self.assertIsInstance(case_property, ConstantValue)

    def test_asdataclass_invalid(self):
        spam_doc = SpamDoc.wrap({
            "spam": {"eggs": "spam"}
        })
        with self.assertRaises(TypeError):
            asdataclass(dict(spam_doc.spam))

    def test_get_commcare_value_case_property(self):
        case_property = asdataclass({"case_property": "spam"})
        info = CaseTriggerInfo(
            domain=DOMAIN,
            case_id="c0ffee",
            type="case",
            extra_fields={
                "spam": "spam spam spam",
            },
        )
        value = get_commcare_value(case_property, info)
        self.assertEqual(value, "spam spam spam")

    def test_get_commcare_value_form_question(self):
        form_question = asdataclass({"form_question": "/data/spam"})
        info = CaseTriggerInfo(
            domain=DOMAIN,
            case_id="c0ffee",
            type="case",
            form_question_values={
                "/data/spam": "spam spam spam",
            },
        )
        value = get_commcare_value(form_question, info)
        self.assertEqual(value, "spam spam spam")

    def test_get_commcare_value_constant_value(self):
        constant_value = asdataclass({"value": "spam spam spam"})
        info = CaseTriggerInfo(
            domain=DOMAIN,
            case_id="c0ffee",
            type="case",
        )
        value = get_commcare_value(constant_value, info)
        self.assertEqual(value, "spam spam spam")


@singledispatch
def get_commcare_value(value_source, case_trigger_info):
    raise TypeError(
        f'Unrecognised value source type: {type(value_source)}'
    )


@get_commcare_value.register(ConstantValue)
def get_constant_value(value_source, case_trigger_info):
    serializer = (
        serializers.get((value_source.value_data_type, value_source.commcare_data_type))
        or serializers.get((None, value_source.commcare_data_type))
    )
    return serializer(value_source.value) if serializer else value_source.value


@get_commcare_value.register(FormQuestion)
def get_form_question_value(value_source, case_trigger_info):
    return case_trigger_info.form_question_values.get(
        value_source.form_question
    )


@get_commcare_value.register(CaseProperty)
def get_case_property_value(value_source, case_trigger_info):
    if value_source.case_property in case_trigger_info.updates:
        return case_trigger_info.updates[value_source.case_property]
    return case_trigger_info.extra_fields.get(value_source.case_property)
