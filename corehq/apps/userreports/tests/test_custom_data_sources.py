import os
from django.test import SimpleTestCase
from django.test.utils import override_settings
from corehq.apps.app_manager.tests import TestFileMixin
from corehq.apps.userreports.models import CustomDataSourceConfiguration


class TestCustomDataSource(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'custom_data_sources')
    root = os.path.dirname(__file__)

    def test_wrap(self):
        wrapped = CustomDataSourceConfiguration.wrap(self.get_json('sample_custom_data_source'))
        self.assertEqual(["example", "dimagi"], wrapped.domains)

    def test_get_all(self):
        with override_settings(STATIC_DATA_SOURCES=[self.get_path('sample_custom_data_source', 'json')]):
            all = list(CustomDataSourceConfiguration.all())
            self.assertEqual(2, len(all))
            example, dimagi = all
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in all:
                self.assertEqual('all_candidates', config.table_id)

    def test_production_config(self):
        for data_source in CustomDataSourceConfiguration.all():
            data_source.validate()
