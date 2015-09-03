import os
from django.test import SimpleTestCase
from django.test.utils import override_settings
from corehq.apps.app_manager.tests import TestFileMixin
from corehq.apps.userreports.models import StaticDataSourceConfiguration


class TestStaticDataSource(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'static_data_sources')
    root = os.path.dirname(__file__)

    def test_wrap(self):
        wrapped = StaticDataSourceConfiguration.wrap(self.get_json('sample_static_data_source'))
        self.assertEqual(["example", "dimagi"], wrapped.domains)

    def test_get_all(self):
        with override_settings(STATIC_DATA_SOURCES=[self.get_path('sample_static_data_source', 'json')]):
            all = list(StaticDataSourceConfiguration.all())
            self.assertEqual(2, len(all))
            example, dimagi = all
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in all:
                self.assertEqual('all_candidates', config.table_id)

    def test_production_config(self):
        for data_source in StaticDataSourceConfiguration.all():
            data_source.validate()
