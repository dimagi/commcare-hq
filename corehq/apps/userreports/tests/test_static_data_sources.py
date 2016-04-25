import os
import uuid
from django.test import SimpleTestCase
from django.test.utils import override_settings
from mock import patch, MagicMock

from corehq.apps.userreports.tests.utils import domain_lite
from corehq.util.test_utils import TestFileMixin
from corehq.apps.userreports.models import StaticDataSourceConfiguration, DataSourceConfiguration


@patch('corehq.apps.callcenter.data_source.get_call_center_domains', MagicMock(return_value=[domain_lite('cc1')]))
class TestStaticDataSource(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'static_data_sources')
    root = os.path.dirname(__file__)

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

            for config in all[3:]:
                self.assertEqual('cc1', config.domain)

    def test_is_static_positive(self):
        with override_settings(STATIC_DATA_SOURCES=[self.get_path('sample_static_data_source', 'json')]):
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
        for data_source in StaticDataSourceConfiguration.all():
            data_source.validate()
