from unittest.mock import patch

from corehq.apps.callcenter.tests.test_utils import CallCenterDomainMockTest
from corehq.apps.userreports.models import StaticDataSourceConfiguration


class BasePillowTestCase(CallCenterDomainMockTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Time savings: ~25s per
        #   DataSourceProvider.get_data_sources() et al and/or
        #   ConfigurableReportTableManager.bootstrap()
        cls.patches = [
            patch.object(StaticDataSourceConfiguration, "_all", lambda: []),
            patch("corehq.apps.userreports.pillow.rebuild_sql_tables"),
        ]
        for px in cls.patches:
            px.start()

    @classmethod
    def tearDownClass(cls):
        for px in cls.patches:
            px.stop()
        super().tearDownClass()
