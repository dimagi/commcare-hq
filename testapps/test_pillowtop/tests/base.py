from unittest.mock import patch

from corehq.apps.callcenter.tests.test_utils import CallCenterDomainMockTest
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.pillow import ConfigurableReportTableManager


class BasePillowTestCase(CallCenterDomainMockTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Time savings: ~25s per
        #   DataSourceProvider.get_data_sources() et al and/or
        #   ConfigurableReportTableManager.bootstrap()
        # and @run_with_all_backends is a multiplier
        cls.patches = [
            patch.object(StaticDataSourceConfiguration, "_all", lambda: []),
            patch.object(ConfigurableReportTableManager, "rebuild_tables_if_necessary"),
        ]
        for px in cls.patches:
            px.start()

    @classmethod
    def tearDownClass(cls):
        for px in cls.patches:
            px.stop()
        super().tearDownClass()
