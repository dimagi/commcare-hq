from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.fixtures.dbaccessors import get_fixture_data_types_in_domain, \
    get_number_of_fixture_data_types_in_domain
from corehq.apps.fixtures.models import FixtureDataType


class DBAccessorTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DBAccessorTest, cls).setUpClass()
        cls.domain = 'fixture-dbaccessors'
        cls.data_types = [
            FixtureDataType(domain=cls.domain, tag='a'),
            FixtureDataType(domain=cls.domain, tag='b'),
            FixtureDataType(domain=cls.domain, tag='c'),
            FixtureDataType(domain='other-domain', tag='x'),
        ]
        FixtureDataType.get_db().bulk_save(cls.data_types)
        get_fixture_data_types_in_domain.clear(cls.domain)

    @classmethod
    def tearDownClass(cls):
        FixtureDataType.get_db().bulk_delete(cls.data_types)
        get_fixture_data_types_in_domain.clear(cls.domain)
        super(DBAccessorTest, cls).tearDownClass()

    def test_get_number_of_fixture_data_types_in_domain(self):
        self.assertEqual(
            get_number_of_fixture_data_types_in_domain(self.domain),
            len([data_type for data_type in self.data_types
                 if data_type.domain == self.domain])
        )

    def test_get_fixture_data_types_in_domain(self):
        expected = [data_type.to_json() for data_type in self.data_types if data_type.domain == self.domain]
        actual = [o.to_json() for o in get_fixture_data_types_in_domain(self.domain)]
        self.assertItemsEqual(actual, expected)
