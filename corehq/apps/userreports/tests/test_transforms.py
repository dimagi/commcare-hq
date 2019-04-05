from __future__ import absolute_import
from __future__ import unicode_literals
import six
from datetime import datetime, timedelta, date
from django.test import SimpleTestCase
from mock import patch

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.transforms.factory import TransformFactory
from corehq.apps.userreports.transforms.specs import CustomTransform
from corehq.util.test_utils import generate_cases


class TransformFactoryTest(SimpleTestCase):

    def testMissingType(self):
        with self.assertRaises(BadSpecError):
            TransformFactory.get_transform({
                "custom_type": "user_display"
            })

    def testInvalidType(self):
        with self.assertRaises(BadSpecError):
            TransformFactory.get_transform({
                "type": "not_a_transform_type",
                "custom_type": "user_display"
            })


class NumberFormatTransformTest(SimpleTestCase):

    def setUp(self):
        self.transform = TransformFactory.get_transform({
            "type": "number_format",
            "format_string": "{0:.0f}"
        }).get_transform_function()

    def test_int(self):
        self.assertEqual('11', self.transform(11))

    def test_decimal(self):
        self.assertEqual('11', self.transform(11.23))

    def test_none(self):
        self.assertEqual(None, self.transform(None))


@generate_cases((
    ('11', '11'),
    ('11.23', '11'),
    ('notanumber', 'notanumber'),
    ('', ''),
), NumberFormatTransformTest)
def test_number_format_transform_strings(self, input, expected_result):
    self.assertEqual(expected_result, self.transform(input))


class TestEthiopianConversion(SimpleTestCase):
    '''Tests converting ethiopian string dates to gregorian dates and vice versa'''


@generate_cases((
    ('2009-09-11 ', date(2017, 5, 19)),
    ('2009-13-5 ', date(2017, 9, 10)),
    ('2009_13_11 ', ''),
    ('abc-13-11', ''),
    (None, ''),
), TestEthiopianConversion)
def test_ethiopian_to_gregorian(self, date_string, expected_result):
    transform = TransformFactory.get_transform({
        "type": "custom",
        "custom_type": "ethiopian_date_to_gregorian_date",
    }).get_transform_function()
    self.assertEqual(expected_result, transform(date_string))


@generate_cases((
    (date(2017, 5, 19), '2009-09-11'),
    (date(2017, 9, 10), '2009-13-05'),
    (None, ''),
    ('2017-05-19 ', '2009-09-11'),
    ('2017-5-19', '2009-09-11')
), TestEthiopianConversion)
def test_gregorian_to_ethiopian(self, date_string, expected_result):
    transform = TransformFactory.get_transform({
        "type": "custom",
        "custom_type": "gregorian_date_to_ethiopian_date",
    }).get_transform_function()

    self.assertEqual(expected_result, transform(date_string))


class CustomTransformTest(SimpleTestCase):

    def testInvalidCustomType(self):
        with self.assertRaises(BadSpecError):
            TransformFactory.get_transform({
                "type": "custom",
                "custom_type": "not_valid"
            })

    def testValidCustom(self):
        transform = TransformFactory.get_transform({
            "type": "custom",
            "custom_type": "user_display"
        })
        self.assertTrue(isinstance(transform, CustomTransform))


class DaysElapsedTransformTest(SimpleTestCase):

    def test_datetime_transform(self):
        transform = TransformFactory.get_transform({
            "type": "custom",
            "custom_type": "days_elapsed_from_date"
        })
        self.assertEqual(transform.transform(datetime.utcnow() - timedelta(days=5)), 5)

    def test_string_transform(self):
        transform = TransformFactory.get_transform({
            "type": "custom",
            "custom_type": "days_elapsed_from_date"
        })
        date = (datetime.utcnow() - timedelta(days=5)).strftime('%Y-%m-%d')
        if six.PY2:
            date = date.decode('utf-8')
        self.assertEqual(transform.transform(date), 5)


class TranslationTransform(SimpleTestCase):

    def test_missing_translation(self):
        transform = TransformFactory.get_transform({
            "type": "translation",
            "translations": {},
        }).get_transform_function()
        self.assertEqual(transform('foo'), 'foo')

    def test_basic_translation(self):
        transform = TransformFactory.get_transform({
            "type": "translation",
            "translations": {
                "#0000FF": "Blue"
            },
        }).get_transform_function()
        self.assertEqual(transform('#0000FF'), 'Blue')
        self.assertEqual(transform('#123456'), '#123456')

    def test_default_language_translation(self):
        transform = TransformFactory.get_transform({
            "type": "translation",
            "translations": {
                "#0000FF": {
                    "en": "Blue",
                    "es": "Azul",
                },
                "#800080": {
                    "en": "Purple",
                    "es": "Morado",
                }
            },
        }).get_transform_function()
        self.assertEqual(transform('#0000FF'), 'Blue')
        self.assertEqual(transform('#800080'), 'Purple')
        self.assertEqual(transform('#123456'), '#123456')

    @patch('corehq.apps.userreports.transforms.specs.get_language', lambda: "es")
    def test_spanish_language_translation(self):
        transform = TransformFactory.get_transform({
            "type": "translation",
            "translations": {
                "#0000FF": {
                    "en": "Blue",
                    "es": "Azul",
                },
                "#800080": {
                    "en": "Purple",
                    "es": "Morado",
                }
            },
        }).get_transform_function()
        self.assertEqual(transform('#0000FF'), 'Azul')
        self.assertEqual(transform('#800080'), 'Morado')
        self.assertEqual(transform('#123456'), '#123456')

    def test_dont_translate_for_mobile(self):
        transform = TransformFactory.get_transform({
            "type": "translation",
            "mobile_or_web": "mobile",
            "translations": {
                "#0000FF": "Blue",
                "#800080": [["en", "Purple"], ["es", "Morado"]],  # legacy, mobile-only format
            },
        }).get_transform_function()
        self.assertEqual(transform('#0000FF'), '#0000FF')
        self.assertEqual(transform('#800080'), '#800080')
        self.assertEqual(transform('#123456'), '#123456')

    def test_bad_option(self):
        with self.assertRaises(BadSpecError):
            TransformFactory.get_transform({
                "type": "translation",
                "mobile_or_web": "neither!",
                "translations": {
                    "0": "zero",
                    "1": {"en": "one", "es": "uno"},
                    "2": {"en": "two", "es": "dos"}
                },
            })


class MultiValueStringTranslationTransform(SimpleTestCase):

    def test_multi_translation(self):
        transform = TransformFactory.get_transform({
            "type": "multiple_value_string_translation",
            "translations": {
                "#0000FF": "Blue",
                "#800080": "Purple"
            },
            "delimiter": " "
        }).get_transform_function()
        self.assertEqual(transform('#0000FF #800080'), 'Blue Purple')
        self.assertEqual(transform('#800080 #123456'), 'Purple #123456')
        self.assertEqual(transform('#123 #123456'), '#123 #123456')
        self.assertEqual(transform("#0000FF"), "Blue")
