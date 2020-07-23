import doctest
import warnings

from django.test import SimpleTestCase

import attr
from schema import Use

import corehq.motech.value_source
from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
    DIRECTION_BOTH,
    DIRECTION_EXPORT,
    DIRECTION_IMPORT,
)
from corehq.motech.exceptions import JsonpathError
from corehq.motech.value_source import (
    CaseOwnerAncestorLocationField,
    CaseProperty,
    CasePropertyConstantValue,
    CaseTriggerInfo,
    ConstantValue,
    FormUserAncestorLocationField,
    ValueSource,
    as_value_source,
    get_form_question_values,
)


class GetFormQuestionValuesTests(SimpleTestCase):

    def test_unicode_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': 'b\u0105z'}}})
        self.assertEqual(value, {'/data/foo/bar': 'b\u0105z'})

    def test_unicode_question(self):
        value = get_form_question_values({'form': {'foo': {'b\u0105r': 'baz'}}})
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
                '@xmlns': 'http://openrosa.org/formdesigner/04279622',
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
            '/metadata/xmlns': 'http://openrosa.org/formdesigner/04279622',
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
        case_property = as_value_source({"case_property": "foo"})
        self.assertIsInstance(case_property, CaseProperty)
        self.assertEqual(case_property.case_property, "foo")

    def test_blank_case_property(self):
        with self.assertRaisesRegex(TypeError, "Unable to determine class for {'case_property': ''}"):
            as_value_source({"case_property": ""})

    def test_missing_case_property(self):
        with self.assertRaisesRegex(TypeError, "Unable to determine class for {}"):
            as_value_source({})

    def test_null_case_property(self):
        with self.assertRaisesRegex(TypeError, "Unable to determine class for {'case_property': None}"):
            as_value_source({"case_property": None})

    def test_doc_type(self):
        case_property = as_value_source({
            "doc_type": "CaseProperty",
            "case_property": "foo",
        })
        self.assertIsInstance(case_property, CaseProperty)
        self.assertEqual(case_property.case_property, "foo")
        with self.assertRaises(AttributeError):
            case_property.doc_type


class ConstantValueTests(SimpleTestCase):

    def test_get_commcare_value(self):
        """
        get_commcare_value() should convert from value data type to
        CommCare data type
        """
        one = as_value_source({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_INTEGER,
            "external_data_type": COMMCARE_DATA_TYPE_TEXT,
        })
        self.assertEqual(one.get_commcare_value('foo'), 1)

    def test_serialize(self):
        """
        serialize() should convert from CommCare data type to external
        data type
        """
        one = as_value_source({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_INTEGER,
            "external_data_type": COMMCARE_DATA_TYPE_TEXT,
        })
        self.assertEqual(one.serialize(1), '1')

    def test_deserialize(self):
        """
        deserialize() should convert from external data type to CommCare
        data type
        """
        one = as_value_source({
            "value": 1.0,
            "value_data_type": COMMCARE_DATA_TYPE_DECIMAL,
            "commcare_data_type": COMMCARE_DATA_TYPE_TEXT,
            "external_data_type": COMMCARE_DATA_TYPE_INTEGER,
        })
        self.assertEqual(one.deserialize("foo"), '1')


class JsonPathCasePropertyTests(SimpleTestCase):

    def test_blank_path(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "",
        })
        with self.assertRaises(JsonpathError):
            value_source.get_import_value(json_doc)

    def test_no_values(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "foo.qux",
        })
        external_value = value_source.get_import_value(json_doc)
        self.assertIsNone(external_value)

    def test_one_value(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "foo.bar",
        })
        external_value = value_source.get_import_value(json_doc)
        self.assertEqual(external_value, "baz")

    def test_many_values(self):
        json_doc = {"foo": [{"bar": "baz"}, {"bar": "qux"}]}
        value_source = as_value_source({
            "case_property": "bar",
            "jsonpath": "foo[*].bar",
        })
        external_value = value_source.get_import_value(json_doc)
        self.assertEqual(external_value, ["baz", "qux"])


class CasePropertyConstantValueTests(SimpleTestCase):

    def test_one_value(self):
        json_doc = {"foo": {"bar": "baz"}}
        value_source = as_value_source({
            "case_property": "baz",
            "value": "qux",
            "jsonpath": "foo.bar",
        })
        external_value = value_source.get_import_value(json_doc)
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


class AsJsonObjectTests(SimpleTestCase):

    def test_constant_value_schema_validates_constant_string(self):
        json_object = as_value_source({"value": "spam"})
        self.assertIsInstance(json_object, ConstantValue)

    def test_case_property_constant_value(self):
        json_object = as_value_source({
            "case_property": "spam",
            "value": "spam",
        })
        self.assertIsInstance(json_object, CasePropertyConstantValue)


class FormUserAncestorLocationFieldTests(SimpleTestCase):

    def test_with_form_user_ancestor_location_field(self):
        json_object = as_value_source({"form_user_ancestor_location_field": "dhis_id"})
        self.assertIsInstance(json_object, FormUserAncestorLocationField)
        self.assertEqual(json_object.form_user_ancestor_location_field, "dhis_id")

    def test_with_form_user_ancestor_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "FormUserAncestorLocationField",
            "form_user_ancestor_location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, FormUserAncestorLocationField)
        self.assertEqual(json_object.form_user_ancestor_location_field, "dhis_id")

    def test_with_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "FormUserAncestorLocationField",
            "location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, FormUserAncestorLocationField)
        self.assertEqual(json_object.form_user_ancestor_location_field, "dhis_id")

    def test_with_location(self):
        with self.assertRaises(TypeError):
            as_value_source({"location_field": "dhis_id"})


class CaseOwnerAncestorLocationFieldTests(SimpleTestCase):

    def test_with_form_user_ancestor_location_field(self):
        json_object = as_value_source({"case_owner_ancestor_location_field": "dhis_id"})
        self.assertIsInstance(json_object, CaseOwnerAncestorLocationField)
        self.assertEqual(json_object.case_owner_ancestor_location_field, "dhis_id")

    def test_with_form_user_ancestor_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "CaseOwnerAncestorLocationField",
            "case_owner_ancestor_location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, CaseOwnerAncestorLocationField)
        self.assertEqual(json_object.case_owner_ancestor_location_field, "dhis_id")

    def test_with_location_field_doc_type(self):
        json_object = as_value_source({
            "doc_type": "CaseOwnerAncestorLocationField",
            "location_field": "dhis_id",
        })
        self.assertIsInstance(json_object, CaseOwnerAncestorLocationField)
        self.assertEqual(json_object.case_owner_ancestor_location_field, "dhis_id")

    def test_with_location(self):
        with self.assertRaises(TypeError):
            as_value_source({"location_field": "dhis_id"})


class AsValueSourceTests(SimpleTestCase):

    def test_as_value_source(self):

        @attr.s(auto_attribs=True, kw_only=True)
        class StringValueSource(ValueSource):
            test_value: str

            @classmethod
            def get_schema_params(cls):
                (schema, *other_args), kwargs = super().get_schema_params()
                schema.update({"test_value": Use(str)})  # Casts value as string
                return (schema, *other_args), kwargs

        data = {"test_value": 10}
        value_source = as_value_source(data)
        self.assertEqual(data, {"test_value": 10})
        self.assertIsInstance(value_source, StringValueSource)
        self.assertEqual(value_source.test_value, "10")


def test_doctests():
    results = doctest.testmod(corehq.motech.value_source, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
