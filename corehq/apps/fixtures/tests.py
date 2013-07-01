from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound
from datetime import date
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.fixtures import fixturegenerators
from corehq.apps.fixtures.ctable_backend import CouchFixtureBackend
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership
from corehq.apps.users.models import CommCareUser
from django.test import TestCase
from ctable.backends import CompatibilityException
from ctable.models import SqlExtractMapping, ColumnDef, KeyMatcher
from dimagi.utils.couch.bulk import CouchTransaction


class FixtureDataTest(TestCase):
    def setUp(self):
        self.domain = 'qwerty'

        self.data_type = FixtureDataType(
            domain=self.domain,
            tag="contact",
            name="Contact",
            fields=['name', 'number']
        )
        self.data_type.save()

        self.data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type.get_id,
            fields={
                'name': 'John',
                'number': '+15555555555'
            }
        )
        self.data_item.save()

        self.user = CommCareUser.create(self.domain, 'rudolph', '***')

        self.fixture_ownership = FixtureOwnership(
            domain=self.domain,
            owner_id=self.user.get_id,
            owner_type='user',
            data_item_id=self.data_item.get_id
        )
        self.fixture_ownership.save()

    def tearDown(self):
        self.data_type.delete()
        self.data_item.delete()
        self.user.delete()
        self.fixture_ownership.delete()

    def test_xml(self):
        check_xml_line_by_line(self, """
        <contact>
            <name>John</name>
            <number>+15555555555</number>
        </contact>
        """, ElementTree.tostring(self.data_item.to_xml()))

    def test_ownership(self):
        self.assertItemsEqual([self.data_item.get_id], FixtureDataItem.by_user(self.user, wrap=False))
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))

        fixture, = fixturegenerators.item_lists(self.user)

        check_xml_line_by_line(self, """
        <fixture id="item-list:contact" user_id="%s">
            <contact_list>
                <contact>
                    <name>John</name>
                    <number>+15555555555</number>
                </contact>
            </contact_list>
        </fixture>
        """ % self.user.user_id, ElementTree.tostring(fixture))

        self.data_item.remove_user(self.user)
        self.assertItemsEqual([], self.data_item.get_all_users())

        self.fixture_ownership = self.data_item.add_user(self.user)
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))


class FixtureBackendTests(TestCase):
    def setUp(self):
        self.backend = CouchFixtureBackend()

    def tearDown(self):
        try:
            type = FixtureDataType.get('CtableFixtureType_test_table')
            with CouchTransaction() as transaction:
                type.recursive_delete(transaction)
        except ResourceNotFound:
            pass

    def test_init_data_type(self):
        mapping = SqlExtractMapping(domains=['test'],
                                    name='table',
                                    columns=[
                                        ColumnDef(name="col_a", data_type="string", value_source='key', value_index=1),
                                        ColumnDef(name="col_b", data_type="date", value_source='key', value_index=2),
                                        ColumnDef(name="col_c", data_type="integer", value_source='value',
                                                       match_keys=[KeyMatcher(index=1, value="c")]),
                                        ColumnDef(name="col_d", data_type="datetime", value_source='value',
                                                       match_keys=[KeyMatcher(index=1, value="d")])
                                    ])

        self.backend.init_data_type(mapping)

        data_type = FixtureDataType.get('CtableFixtureType_test_table')
        fields = data_type.fields
        self.assertIn('col_a', fields)
        self.assertIn('col_b', fields)
        self.assertIn('col_c', fields)
        self.assertIn('col_d', fields)

    def test_update_data_type(self):
        self.test_init_data_type()
        self.test_init_data_type()

    def test_update_data_type_add_field(self):
        self.test_init_data_type()
        mapping = SqlExtractMapping(domains=['test'],
                                    name='table',
                                    columns=[
                                        ColumnDef(name="col_a", data_type="string", value_source='key', value_index=1),
                                        ColumnDef(name="col_b", data_type="date", value_source='key', value_index=2),
                                        ColumnDef(name="col_e", data_type="integer", value_source='value',
                                                       match_keys=[KeyMatcher(index=1, value="e")])
                                    ])

        self.backend.init_data_type(mapping)

        data_type = FixtureDataType.get('CtableFixtureType_test_table')
        fields = data_type.fields
        self.assertIn('col_a', fields)
        self.assertIn('col_b', fields)
        self.assertIn('col_c', fields)
        self.assertIn('col_d', fields)
        self.assertIn('col_e', fields)

    def test_update_data_type_fail(self):
        self.test_init_data_type()

        mapping = SqlExtractMapping(domains=['test'],
                                    name='table',
                                    columns=[
                                        ColumnDef(name="col_e", data_type="string", value_source='key', value_index=1)
                                    ])

        with self.assertRaises(CompatibilityException):
            self.backend.init_data_type(mapping)

    def test_check_mapping_missing_column_in_table(self):
        self.test_init_data_type()

        extract = SqlExtractMapping(domains=['test'], name='table', couch_view="c/view", columns=[
            ColumnDef(name="col_a", data_type="string", value_source='key', value_index=1),
            ColumnDef(name="col_b", data_type="date", value_source='key', value_index=2),
            ColumnDef(name="col_d", data_type="datetime", value_source='value',
                           match_keys=[KeyMatcher(index=1, value="d")]),
        ])

        messages = self.backend.check_mapping(extract)

        self.assertEqual(len(messages['errors']), 0)
        self.assertEqual(messages['warnings'], ['Field exists in FixtureDataType but not in mapping: col_c'])

    def test_check_mapping_missing_key_column_in_mapping(self):
        self.test_init_data_type()

        extract = SqlExtractMapping(domains=['test'], name='table', couch_view="c/view", columns=[
            ColumnDef(name="col_a", data_type="string", value_source='key', value_index=1),
            ColumnDef(name="col_b", data_type="date", value_source='key', value_index=2),
            ColumnDef(name="col_e", data_type="date", value_source='key', value_index=2),
            ColumnDef(name="col_c", data_type="integer", value_source='value',
                           match_keys=[KeyMatcher(index=1, value="c")]),
            ColumnDef(name="col_d", data_type="datetime", value_source='value',
                           match_keys=[KeyMatcher(index=1, value="d")]),
        ])

        messages = self.backend.check_mapping(extract)

        self.assertEqual(len(messages['warnings']), 0)
        self.assertEqual(messages['errors'], ['Key column exists in mapping but not in FixtureDataType: col_e'])

    def test_write_data(self):
        mapping = SqlExtractMapping(domains=['test'],
                                    name='table',
                                    columns=[
                                        ColumnDef(name="col_a", data_type="string", value_source='key', value_index=1),
                                        ColumnDef(name="col_b", data_type="date", value_source='key', value_index=2),
                                        ColumnDef(name="col_c", data_type="integer", value_source='value',
                                                       match_keys=[KeyMatcher(index=1, value="c")]),
                                        ColumnDef(name="col_d", data_type="integer", value_source='value',
                                                       match_keys=[KeyMatcher(index=1, value="d")])
                                    ])

        rows = [dict(col_a='one', col_b=date(2013, 01, 01), col_c=3, col_d=4),
                dict(col_a='two', col_b=date(2013, 01, 02), col_c=2, col_d=5)]
        self.backend.write_rows(rows, mapping)

        one = FixtureDataItem.get('CtableFixtureItem_one_2013-01-01')
        self.assertEqual(one.fields['col_c'], 3)
        self.assertEqual(one.fields['col_d'], 4)

        two = FixtureDataItem.get('CtableFixtureItem_two_2013-01-02')
        self.assertEqual(two.fields['col_c'], 2)
        self.assertEqual(two.fields['col_d'], 5)

    def test_write_data_update(self):
        mapping = SqlExtractMapping(domains=['test'],
                                    name='table',
                                    columns=[
                                        ColumnDef(name="col_a", data_type="string", value_source='key', value_index=1),
                                        ColumnDef(name="col_b", data_type="date", value_source='key', value_index=2),
                                        ColumnDef(name="col_c", data_type="integer", value_source='value',
                                                       match_keys=[KeyMatcher(index=1, value="c")]),
                                        ColumnDef(name="col_d", data_type="integer", value_source='value',
                                                       match_keys=[KeyMatcher(index=1, value="d")])
                                    ])

        rows = [dict(col_a='one', col_b=date(2013, 01, 01), col_c=3),
                dict(col_a='one', col_b=date(2013, 01, 01), col_d=5)]
        self.backend.write_rows(rows, mapping)

        one = FixtureDataItem.get('CtableFixtureItem_one_2013-01-01')
        self.assertEqual(one.fields['col_c'], 3)
        self.assertEqual(one.fields['col_d'], 5)
