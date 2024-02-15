from contextlib import contextmanager
from datetime import datetime

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.export.const import DEID_DATE_TRANSFORM, DEID_ID_TRANSFORM
from corehq.apps.hqcase.case_helper import CaseCopier
from corehq.apps.hqcase.utils import (
    get_case_value,
    get_deidentified_data,
    is_copied_case,
)
from corehq.form_processor.tests.utils import create_case

DOMAIN = 'test-domain'


class TestGetCaseValue(TestCase):

    def test_value_is_case_attribute(self):
        attr_value = 'external_id'
        attr = 'external_id'

        with get_case(**{attr: attr_value}) as case:
            case_value, is_property = get_case_value(case, attr)

        self.assertFalse(is_property)
        self.assertEqual(case_value, attr_value)

    def test_value_is_case_property(self):
        properties = {
            'captain': 'Jack Sparrow'
        }

        with get_case(update=properties) as case:
            case_value, is_property = get_case_value(case, 'captain')

        self.assertTrue(is_property)
        self.assertEqual(case_value, 'Jack Sparrow')

    def test_value_does_not_exist(self):
        with get_case() as case:
            case_value, is_property = get_case_value(case, 'non-existing-property')

        self.assertTrue(case_value is None)
        self.assertTrue(is_property is None)

    def test_no_value_provided_results_in_none(self):
        with get_case() as case:
            case_value, is_property = get_case_value(case, '')

        self.assertTrue(case_value is None)
        self.assertTrue(is_property is None)


class TestGetCensoredCaseData(TestCase):

    def test_no_censor_data_provided(self):
        with get_case() as case:
            censored_attrs, censored_props = get_deidentified_data(case, {})

        self.assertTrue(censored_attrs == censored_props == {})

    def test_valid_attributes_and_properties(self):
        properties = {
            'captain': 'Jack Sparrow',
        }
        attrs = {
            'external_id': 'external_id',
            'date_opened': str(datetime.utcnow()),
        }
        censor_data = {
            'date_opened': DEID_DATE_TRANSFORM,
            'captain': DEID_ID_TRANSFORM,
        }
        with get_case(update=properties, **attrs) as case:
            censored_attrs, censored_props = get_deidentified_data(case, censor_data)

        self.assertTrue(properties['captain'] != censored_props['captain'])
        self.assertTrue(attrs['date_opened'] != censored_attrs['date_opened'])

    def test_missing_properties(self):
        censor_data = {
            'captain': DEID_ID_TRANSFORM,
        }
        with get_case() as case:
            censored_attrs, censored_props = get_deidentified_data(case, censor_data)

        self.assertTrue(censored_attrs == censored_props == {})

    def test_invalid_deid_transform_blanks_property(self):
        properties = {
            'captain': 'Jack Sparrow',
        }
        censor_data = {
            'captain': 'invalid_deid_transform',
        }
        with get_case(update=properties) as case:
            censored_attrs, censored_props = get_deidentified_data(case, censor_data)

        self.assertTrue(censored_attrs == {})
        self.assertTrue(censored_props['captain'] == '')


@contextmanager
def get_case(*args, **kwargs):
    factory = CaseFactory(DOMAIN)
    case = factory.create_case(
        case_type='ship',
        case_name='Black Pearl',
        **kwargs,
    )
    try:
        yield case
    finally:
        factory.close_case(case.case_id)


class TestIsCopiedCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_1 = create_case(domain=DOMAIN, name='case_1', case_json={'type': 'original'})
        cls.case_2 = create_case(
            domain=DOMAIN,
            name='case_2',
            case_json={'type': 'copied', CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME: cls.case_1.case_id}
        )

    def test_is_copied_case(self):
        self.assertFalse(is_copied_case(self.case_1))
        self.assertTrue(is_copied_case(self.case_2))
