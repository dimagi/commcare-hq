from datetime import datetime

from django.test import TestCase
from contextlib import contextmanager
from casexml.apps.case.mock import CaseFactory
from couchexport.deid import deid_date, deid_ID

from corehq.apps.hqcase.utils import (
    get_case_value,
    get_censored_case_data,
)

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
            censored_attrs, censored_props = get_censored_case_data(case, {})

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
            'date_opened': self.date_transform,
            'captain': self.id_transform,
        }
        with get_case(update=properties, **attrs) as case:
            censored_attrs, censored_props = get_censored_case_data(case, censor_data)

        self.assertTrue(properties['captain'] != censored_props['captain'])
        self.assertTrue(attrs['date_opened'] != censored_attrs['date_opened'])

    def test_missing_properties(self):
        censor_data = {
            'captain': self.id_transform,
        }
        with get_case() as case:
            censored_attrs, censored_props = get_censored_case_data(case, censor_data)

        self.assertTrue(censored_attrs == censored_props == {})

    def test_invalid_deid_transform_blanks_property(self):
        properties = {
            'captain': 'Jack Sparrow',
        }
        censor_data = {
            'captain': self.invalid_transform,
        }
        with get_case(update=properties) as case:
            censored_attrs, censored_props = get_censored_case_data(case, censor_data)

        self.assertTrue(censored_attrs == {})
        self.assertTrue(censored_props['captain'] == '')

    @property
    def date_transform(self):
        return deid_date.__name__

    @property
    def id_transform(self):
        return deid_ID.__name__

    @property
    def invalid_transform(self):
        return 'invalid'


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
