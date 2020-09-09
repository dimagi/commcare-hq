from django.test import TestCase

from corehq.motech.dhis2.const import SEND_FREQUENCY_MONTHLY
from corehq.motech.dhis2.dbaccessors import get_migrated_dataset_maps
from corehq.motech.dhis2.models import DataSetMap, SQLDataSetMap
from corehq.motech.models import ConnectionSettings


class MigrationTest(TestCase):

    domain = 'test-domain'

    def setUp(self):
        self.connx = ConnectionSettings.objects.create(
            domain=self.domain,
            name='test connection',
            url='https://dhis2.example.com/'
        )
        self.dataset_map = DataSetMap.wrap({
            'domain': self.domain,
            'connection_settings_id': self.connx.id,
            'ucr_id': 'c0ffee',
            'description': 'test dataset map',
            'frequency': SEND_FREQUENCY_MONTHLY,
            'day_to_send': 5,
            'org_unit_column': 'org_unit_id',
            'datavalue_maps': [{
                'column': 'foo_bar',
                'data_element_id': 'foo456789ab',
                'category_option_combo_id': 'bar456789ab',
            }, {
                'column': 'foo_baz',
                'data_element_id': 'foo456789ab',
                'category_option_combo_id': 'baz456789ab',
            }, {
                'column': 'foo_qux',
                'data_element_id': 'foo456789ab',
                'category_option_combo_id': 'qux456789ab',
            }]
        })
        self.dataset_map.save()

    def tearDown(self):
        for m in SQLDataSetMap.objects.filter(domain=self.domain).all():
            m.delete()
        self.dataset_map.delete()
        self.connx.delete()

    def test_get_migrated_dataset_maps(self):
        migrated_dataset_maps = get_migrated_dataset_maps(self.domain)
        self.assertEqual(len(migrated_dataset_maps), 1)
        sql_dataset_map = migrated_dataset_maps[0]

        self.assertEqual(sql_dataset_map.description, 'test dataset map')

        self.assertEqual(sql_dataset_map.connection_settings.name,
                         'test connection')

        self.assertEqual(len(sql_dataset_map.datavalue_maps.all()), 3)
        columns = {m.column for m in sql_dataset_map.datavalue_maps.all()}
        self.assertEqual(columns, {'foo_bar', 'foo_baz', 'foo_qux'})
