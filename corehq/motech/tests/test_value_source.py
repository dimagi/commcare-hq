import doctest
import warnings

from django.test import SimpleTestCase

from couchdbkit import BadValueError

import corehq.motech.value_source
from corehq.motech.value_source import CaseProperty, get_form_question_values


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.value_source)
        self.assertEqual(results.failed, 0)


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


class CasePropertyValidationTests(SimpleTestCase):

    def test_valid_case_property(self):
        CaseProperty.wrap({"case_property": "foo"})

    def test_blank_case_property(self):
        with self.assertRaisesRegexp(BadValueError, "Value cannot be blank."):
            CaseProperty.wrap({"case_property": ""})

    def test_missing_case_property(self):
        case_property = CaseProperty.wrap({})
        with self.assertRaisesRegexp(BadValueError, "Property case_property is required."):
            case_property.validate()

    def test_null_case_property(self):
        case_property = CaseProperty.wrap({"case_property": None})
        with self.assertRaisesRegexp(BadValueError, "Property case_property is required."):
            case_property.validate()
