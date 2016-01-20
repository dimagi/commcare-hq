from datetime import datetime, timedelta
from django.test import SimpleTestCase
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
        self.assertEqual(transform.transform(date), 5)
