import doctest
import warnings

from django.test import SimpleTestCase

from couchdbkit import BadValueError
from testil import assert_raises

import corehq.motech.value_source
from corehq.motech.value_source import (
    CaseTriggerInfo,
    ValueSource,
    get_form_question_values,
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
        ValueSource.wrap({
            "doc_type": "CaseProperty",
            "case_property": "foo",
        })

    def test_blank_case_property(self):
        with self.assertRaisesRegex(BadValueError, "Value cannot be blank."):
            ValueSource.wrap({
                "doc_type": "CaseProperty",
                "case_property": "",
            })

    def test_missing_case_property(self):
        case_property = ValueSource.wrap({
            "doc_type": "CaseProperty",
        })
        with self.assertRaisesRegex(BadValueError, "Property case_property is required."):
            case_property.validate()

    def test_null_case_property(self):
        case_property = ValueSource.wrap({
            "doc_type": "CaseProperty",
            "case_property": None,
        })
        with self.assertRaisesRegex(BadValueError, "Property case_property is required."):
            case_property.validate()


class MapTests(SimpleTestCase):

    def test_no_map(self):
        form_question_map = ValueSource.wrap({
            "doc_type": "FormQuestionMap",
            "form_question": "/data/foo/bar",
        })
        with self.assertRaisesRegex(BadValueError, "Property value_map is required."):
            form_question_map.validate()

    def test_empty_map(self):
        form_question_map = ValueSource.wrap({
            "doc_type": "FormQuestionMap",
            "form_question": "/data/foo/bar",
            "value_map": {},
        })
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id=None,
            form_question_values={'/data/foo/bar': 'baz'},
        )
        value = form_question_map.get_value(info)
        self.assertIsNone(value)

    def test_map(self):
        form_question_map = ValueSource.wrap({
            "doc_type": "FormQuestionMap",
            "form_question": "/data/foo/bar",
            "value_map": {
                "baz": 42,
            },
        })
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id=None,
            form_question_values={'/data/foo/bar': 'baz'},
        )
        value = form_question_map.get_value(info)
        self.assertEqual(value, 42)

    def test_map_missing_value(self):
        form_question_map = ValueSource.wrap({
            "doc_type": "FormQuestionMap",
            "form_question": "/data/foo/bar",
            "value_map": {
                "baz": 42,
            },
        })
        info = CaseTriggerInfo(
            domain="test-domain",
            case_id=None,
            form_question_values={'/data/foo/bar': 'qux'},
        )
        value = form_question_map.get_value(info)
        self.assertIsNone(value)

    def test_deserialize_map(self):
        form_question_map = ValueSource.wrap({
            "doc_type": "FormQuestionMap",
            "form_question": "/data/foo/bar",
            "value_map": {
                "baz": 42,
            },
        })
        value = form_question_map.deserialize(42)
        self.assertEqual(value, "baz")

    def test_deserialize_map_missing_value(self):
        form_question_map = ValueSource.wrap({
            "doc_type": "FormQuestionMap",
            "form_question": "/data/foo/bar",
            "value_map": {
                "baz": 42,
            },
        })
        value = form_question_map.deserialize(13)
        self.assertIsNone(value)


def test_dyn_properties():
    with assert_raises(AttributeError):
        ValueSource.wrap({
            "doc_type": "FormQuestion",
            "case_property": "foo",
        })


def test_doctests():
    results = doctest.testmod(corehq.motech.value_source)
    assert results.failed == 0
