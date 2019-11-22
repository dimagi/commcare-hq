import doctest
import warnings

from django.test import SimpleTestCase

from couchdbkit import BadValueError

import corehq.motech.value_source
from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
    DIRECTION_BOTH,
    DIRECTION_EXPORT,
    DIRECTION_IMPORT,
)
from corehq.motech.value_source import (
    CaseProperty,
    CasePropertyConstantValue,
    CaseTriggerInfo,
    ConstantString,
    ConstantValue,
    FormQuestionMap,
    JsonPathCaseProperty,
    ValueSource,
    deserialize,
    get_commcare_value,
    get_form_question_values,
    get_import_value,
    get_value,
    serialize,
)


class GetFormQuestionValuesTests(SimpleTestCase):

    def test_unicode_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': 'b\u0105z'}}})
        self.assertEqual(value, {'/data/foo/bar': 'b\u0105z'})

    def test_utf8_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': b'b\xc4\x85z'}}})
        self.assertEqual(value, {'/data/foo/bar': b'b\xc4\x85z'})

    def test_unicode_question(self):
        value = get_form_question_values({'form': {'foo': {'b\u0105r': 'baz'}}})
        self.assertEqual(value, {'/data/foo/b\u0105r': 'baz'})

    def test_utf8_question(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UnicodeWarning)
            value = get_form_question_values({'form': {'foo': {b'b\xc4\x85r': 'baz'}}})
        self.assertEqual(value, {'/data/foo/b\u0105r': 'baz'})

    def test_received_on(self):
        value = get_form_question_values({
            'form': {
                'foo': {'bar': 'baz'},
            },
            'received_on': '2018-11-06T18:30:00.000000Z',
        })
        self.assertDictEqual(value, {
            '/data/foo/bar': 'baz',
            '/metadata/received_on': '2018-11-06T18:30:00.000000Z',
        })

    def test_metadata(self):
        value = get_form_question_values({
            'form': {
                'foo': {'bar': 'baz'},
                'meta': {
                    'timeStart': '2018-11-06T18:00:00.000000Z',
                    'timeEnd': '2018-11-06T18:15:00.000000Z',
                    'spam': 'ham',
                },
            },
            'received_on': '2018-11-06T18:30:00.000000Z',
        })
        self.assertDictEqual(value, {
            '/data/foo/bar': 'baz',
            '/metadata/timeStart': '2018-11-06T18:00:00.000000Z',
            '/metadata/timeEnd': '2018-11-06T18:15:00.000000Z',
            '/metadata/spam': 'ham',
            '/metadata/received_on': '2018-11-06T18:30:00.000000Z',
        })


class CaseTriggerInfoTests(SimpleTestCase):

    def test_default_attr(self):
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id='c0ffee',
        )
        self.assertIsNone(info.name)

    def test_factory_attr(self):
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id='c0ffee',
        )
        self.assertEqual(info.form_question_values, {})

    def test_required_attr(self):
        with self.assertRaises(TypeError):
            CaseTriggerInfo(
                domain="test-domain",
            )


class CasePropertyValidationTests(SimpleTestCase):

    def test_valid_case_property(self):
        CaseProperty.wrap({"case_property": "foo"})

    def test_blank_case_property(self):
        with self.assertRaisesRegex(BadValueError, "Value cannot be blank."):
            CaseProperty.wrap({"case_property": ""})

    def test_missing_case_property(self):
        case_property = CaseProperty.wrap({})
        with self.assertRaisesRegex(BadValueError, "Property case_property is required."):
            case_property.validate()

    def test_null_case_property(self):
        case_property = CaseProperty.wrap({"case_property": None})
        with self.assertRaisesRegex(BadValueError, "Property case_property is required."):
            case_property.validate()


class ConstantStringTests(SimpleTestCase):

    def test_get_value(self):
        constant = ConstantString.wrap({"value": "foo"})
        info = CaseTriggerInfo("test-domain", None)
        value = get_value(constant, info)
        self.assertEqual(value, "foo")

    def test_default_get_value(self):
        constant = ConstantString.wrap({})
        info = CaseTriggerInfo("test-domain", None)
        value = get_value(constant, info)
        self.assertIsNone(value)

    def test_casting_value(self):
        constant = ConstantString.wrap({
            "value": "1",
            "external_data_type": COMMCARE_DATA_TYPE_DECIMAL,
        })
        info = CaseTriggerInfo("test-domain", None)
        value = get_value(constant, info)
        self.assertEqual(value, 1.0)

    def test_deserialize(self):
        constant = ConstantString.wrap({"value": "foo"})
        external_value = "bar"
        value = deserialize(constant, external_value)
        self.assertIsNone(value)


class ConstantValueTests(SimpleTestCase):

    def test_get_commcare_value(self):
        """
        get_commcare_value() should convert from value data type to
        CommCare data type
        """
        one = ConstantValue.wrap({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_INTEGER,
            "external_data_type": COMMCARE_DATA_TYPE_TEXT,
        })
        self.assertEqual(get_commcare_value(one, 'foo'), 1)

    def test_serialize(self):
        """
        serialize() should convert from CommCare data type to external
        data type
        """
        one = ConstantValue.wrap({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_INTEGER,
            "external_data_type": COMMCARE_DATA_TYPE_TEXT,
        })
        self.assertEqual(serialize(one, 1), '1')

    def test_deserialize(self):
        """
        deserialize() should convert from external data type to CommCare
        data type
        """
        one = ConstantValue.wrap({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_TEXT,
            "external_data_type": COMMCARE_DATA_TYPE_INTEGER,
        })
        self.assertEqual(deserialize(one, "foo"), '1')


class JsonPathCasePropertyTests(SimpleTestCase):

    def test_blank_path(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = JsonPathCaseProperty.wrap({
            "case_property": "bar",
            "jsonpath": "",
        })
        external_value = get_import_value(value_source, json_doc)
        self.assertIsNone(external_value)

    def test_no_values(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = JsonPathCaseProperty.wrap({
            "case_property": "bar",
            "jsonpath": "foo.qux",
        })
        external_value = get_import_value(value_source, json_doc)
        self.assertIsNone(external_value)

    def test_one_value(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = JsonPathCaseProperty.wrap({
            "case_property": "bar",
            "jsonpath": "foo.bar",
        })
        external_value = get_import_value(value_source, json_doc)
        self.assertEqual(external_value, "baz")

    def test_many_values(self):
        json_doc = {"foo": [{"bar": "baz"}, {"bar": "qux"}]}
        value_source = JsonPathCaseProperty.wrap({
            "case_property": "bar",
            "jsonpath": "foo[*].bar",
        })
        external_value = get_import_value(value_source, json_doc)
        self.assertEqual(external_value, ["baz", "qux"])


class CasePropertyConstantValueTests(SimpleTestCase):

    def test_one_value(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = CasePropertyConstantValue.wrap({
            "value": "qux",
            "jsonpath": "foo.bar",
        })
        external_value = get_import_value(value_source, json_doc)
        self.assertEqual(external_value, "qux")


class DirectionTests(SimpleTestCase):

    def test_direction_in_true(self):
        value_source = ValueSource(direction=DIRECTION_IMPORT)
        self.assertTrue(value_source.can_import)

    def test_direction_in_false(self):
        value_source = ValueSource(direction=DIRECTION_IMPORT)
        self.assertFalse(value_source.can_export)

    def test_direction_out_true(self):
        value_source = ValueSource(direction=DIRECTION_EXPORT)
        self.assertTrue(value_source.can_export)

    def test_direction_out_false(self):
        value_source = ValueSource(direction=DIRECTION_EXPORT)
        self.assertFalse(value_source.can_import)

    def test_direction_both_true(self):
        value_source = ValueSource(direction=DIRECTION_BOTH)
        self.assertTrue(value_source.can_import)
        self.assertTrue(value_source.can_export)


def test_doctests():
    results = doctest.testmod(corehq.motech.value_source)
    assert results.failed == 0
