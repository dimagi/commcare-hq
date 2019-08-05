from __future__ import absolute_import
from __future__ import unicode_literals
import os
import uuid
from collections import Counter
from django.test import SimpleTestCase
from django.test.utils import override_settings
from mock import patch, MagicMock

from corehq.apps.userreports.tests.utils import domain_lite
from corehq.util.test_utils import TestFileMixin
from corehq.apps.userreports.models import StaticDataSourceConfiguration, DataSourceConfiguration


class TestStaticDataSource(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'static_data_sources')
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super(TestStaticDataSource, cls).setUpClass()
        with patch('corehq.apps.callcenter.utils.get_call_center_domains',
                   MagicMock(return_value=[domain_lite('cc1')])):
            cls.configs = list(StaticDataSourceConfiguration.all())

    def test_wrap(self):
        wrapped = StaticDataSourceConfiguration.wrap(self.get_json('sample_static_data_source'))
        self.assertEqual(["example", "dimagi"], wrapped.domains)

    def test_get_all(self):
        with override_settings(STATIC_DATA_SOURCES=[self.get_path('sample_static_data_source', 'json')]):
            all = list(StaticDataSourceConfiguration.all())
            self.assertEqual(2 + 3, len(all))
            example, dimagi = all[:2]
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in all[:2]:
                self.assertEqual('all_candidates', config.table_id)

            for config in all[2:]:
                self.assertEqual('cc1', config.domain)

    def test_is_static_positive_json(self):
        with override_settings(STATIC_DATA_SOURCES=[self.get_path('sample_static_data_source', 'json')]):
            example = list(StaticDataSourceConfiguration.all())[0]
            self.assertTrue(example.is_static)

    def test_is_static_positive_yaml(self):
        with override_settings(STATIC_DATA_SOURCES=[self.get_path('sample_static_data_source', 'yaml')]):
            example = list(StaticDataSourceConfiguration.all())[0]
            self.assertTrue(example.is_static)

    def test_is_static_negative(self):
        self.assertFalse(DataSourceConfiguration().is_static)
        self.assertFalse(DataSourceConfiguration(_id=uuid.uuid4().hex).is_static)

    def test_deactivate_noop(self):
        with override_settings(STATIC_DATA_SOURCES=[self.get_path('sample_static_data_source', 'json')]):
            example = list(StaticDataSourceConfiguration.all())[0]
            # since this is a SimpleTest, this should fail if the call actually hits the DB
            example.deactivate()

    def test_production_config(self):
        for data_source in self.configs:
            data_source.validate()

    def test_for_table_id_conflicts(self):
        counts = Counter((ds.table_id, ds.domain) for ds in self.configs)
        duplicates = [k for k, v in counts.items() if v > 1]
        msg = "The following data source configs have duplicate table_ids on the same domains:\n{}".format(
            "\n".join("table_id: {}, domain: {}".format(table_id, domain) for table_id, domain in duplicates)
        )
        self.assertEqual(0, len(duplicates), msg)
