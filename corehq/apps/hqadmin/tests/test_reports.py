from datetime import datetime, timedelta
from uuid import uuid4

from django.test import TestCase
from unittest.mock import patch

from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqadmin.reports import UCRRebuildRestrictionTable, StaleCasesTable
from corehq.form_processor.models import CommCareCase
from corehq.motech.repeaters.const import UCRRestrictionFFStatus


class TestUCRRebuildRestrictionTable(TestCase):

    @patch('corehq.apps.hqadmin.reports.USER_CONFIGURABLE_REPORTS.get_enabled_domains')
    def test_all_ucr_domains(self, get_enabled_domains_mock):
        ucr_enabled_domains = ['domain1', 'domain2']
        get_enabled_domains_mock.return_value = ucr_enabled_domains

        table_data = UCRRebuildRestrictionTable()

        self.assertEqual(
            table_data.ucr_domains,
            ucr_enabled_domains
        )

    def test_should_show_domain_default_show_all(self):
        table_data = UCRRebuildRestrictionTable()
        self.assertTrue(table_data.should_show_domain)

    @patch.object(UCRRebuildRestrictionTable, '_rebuild_restricted_ff_enabled')
    def test_should_show_domain_show_ff_enabled_domains(self, restriction_ff_enabled_mock):
        """ Test domains which does have the FF enabled """
        restriction_ff_enabled_mock.return_value = True

        table_data = UCRRebuildRestrictionTable(
            restriction_ff_status=UCRRestrictionFFStatus.Enabled.name,
        )
        self.assertTrue(table_data.should_show_domain(
            domain='domain', total_cases=100_000_000, total_forms=0)
        )

    @patch.object(UCRRebuildRestrictionTable, '_rebuild_restricted_ff_enabled')
    def test_should_show_domain_show_ff_disabled_domains(self, restriction_ff_enabled_mock):
        """ Test domains which does not have the FF enabled """
        restriction_ff_enabled_mock.return_value = False

        table_data = UCRRebuildRestrictionTable(
            restriction_ff_status=UCRRestrictionFFStatus.NotEnabled.name,
        )
        self.assertTrue(table_data.should_show_domain(
            domain='domain', total_cases=10, total_forms=0)
        )

    @patch.object(UCRRebuildRestrictionTable, '_rebuild_restricted_ff_enabled')
    def test_should_show_domain_show_should_enable_ff_domains(self, restriction_ff_enabled_mock):
        """ Test domains which does not have the FF enabled but should have it enabled """
        restriction_ff_enabled_mock.return_value = False

        table_data = UCRRebuildRestrictionTable(
            restriction_ff_status=UCRRestrictionFFStatus.ShouldEnable.name,
        )
        self.assertTrue(table_data.should_show_domain(
            domain='domain', total_cases=100_000_000, total_forms=0)
        )
        self.assertFalse(table_data.should_show_domain(
            domain='domain', total_cases=10, total_forms=0)
        )

    @patch.object(UCRRebuildRestrictionTable, '_rebuild_restricted_ff_enabled')
    def test_should_show_domain_show_should_disable_ff_domains(self, restriction_ff_enabled_mock):
        """ Test domains which does have the FF enabled but should not have it enabled """
        restriction_ff_enabled_mock.return_value = True

        table_data = UCRRebuildRestrictionTable(
            restriction_ff_status=UCRRestrictionFFStatus.CanDisable.name,
        )
        self.assertTrue(table_data.should_show_domain(
            domain='domain', total_cases=10, total_forms=0)
        )
        self.assertFalse(table_data.should_show_domain(
            domain='domain', total_cases=100_000_000, total_forms=0)
        )


@es_test(requires=[case_search_adapter], setup_class=True)
class TestStaleCasesTable(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cases = [
            cls._get_case(days_back=0),
            cls._get_case(days_back=365),
            cls._get_case(days_back=380, is_closed=True),
            cls._get_case(days_back=365 * 21),
        ]
        case_search_adapter.bulk_index(cases, refresh=True)
        cls.table = StaleCasesTable()

    @classmethod
    def _get_case(cls, days_back, is_closed=False):
        modified_on = datetime.now() - timedelta(days=days_back)
        return CommCareCase(
            case_id=uuid4().hex,
            domain='test',
            modified_on=modified_on,
            closed=is_closed
        )

    @patch.object(StaleCasesTable, '_get_domains')
    def test_get_rows(self, _get_domains_mock):
        _get_domains_mock.return_value = ['test']
        self.assertEqual(
            self.table.rows,
            [['test', 1]]
        )
