from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ..metric_registry import DomainContext
from ..feature_calcs import (
    calc_case_exports_only,
    calc_det_configs,
    calc_form_exports,
    calc_has_case_deduplication,
    calc_has_excel_dashboard,
    calc_case_list_explorer_reports,
    calc_linked_domains,
    calc_odata_feeds,
    calc_scheduled_exports,
    calc_has_data_dictionary,
)


def _make_ctx(form_exports=None, case_exports=None):
    domain_obj = MagicMock()
    domain_obj.name = 'test'
    ctx = DomainContext(domain_obj)
    if form_exports is not None:
        ctx.__dict__['form_exports'] = form_exports
    if case_exports is not None:
        ctx.__dict__['case_exports'] = case_exports
    return ctx


def _make_export(**kwargs):
    export = MagicMock()
    for k, v in kwargs.items():
        setattr(export, k, v)
    return export


class TestCalcHasDataDictionary(SimpleTestCase):

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_false_when_no_case_types(self, mock_ct_manager, mock_cp_manager):
        mock_ct_manager.filter.return_value.exists.return_value = False
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is False

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_true_when_case_type_has_description(
        self, mock_ct_manager, mock_cp_manager
    ):
        qs = mock_ct_manager.filter.return_value
        qs.exists.return_value = True
        qs.exclude.return_value.exclude.return_value.exists.return_value = True
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is True

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_true_when_property_has_description(
        self, mock_ct_manager, mock_cp_manager
    ):
        # case types exist but none have descriptions
        ct_qs = mock_ct_manager.filter.return_value
        ct_qs.exists.return_value = True
        ct_qs.exclude.return_value.exclude.return_value.exists.return_value = False

        # first CaseProperty.objects.filter() call: property descriptions
        cp_qs1 = MagicMock()
        cp_qs1.exclude.return_value.exclude.return_value.exists.return_value = True

        mock_cp_manager.filter.return_value = cp_qs1
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is True

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_true_when_property_has_group(
        self, mock_ct_manager, mock_cp_manager
    ):
        ct_qs = mock_ct_manager.filter.return_value
        ct_qs.exists.return_value = True
        ct_qs.exclude.return_value.exclude.return_value.exists.return_value = False

        # First call: property descriptions - no matches
        cp_qs_desc = MagicMock()
        cp_qs_desc.exclude.return_value.exclude.return_value.exists.return_value = False

        # Second call: property groups - has matches
        cp_qs_group = MagicMock()
        cp_qs_group.exists.return_value = True

        mock_cp_manager.filter.side_effect = [cp_qs_desc, cp_qs_group]
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is True

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_false_when_no_descriptions_or_groups(
        self, mock_ct_manager, mock_cp_manager
    ):
        ct_qs = mock_ct_manager.filter.return_value
        ct_qs.exists.return_value = True
        ct_qs.exclude.return_value.exclude.return_value.exists.return_value = False

        # First call: property descriptions - no matches
        cp_qs_desc = MagicMock()
        cp_qs_desc.exclude.return_value.exclude.return_value.exists.return_value = False

        # Second call: property groups - no matches
        cp_qs_group = MagicMock()
        cp_qs_group.exists.return_value = False

        mock_cp_manager.filter.side_effect = [cp_qs_desc, cp_qs_group]
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is False


class TestCalcFormExports(SimpleTestCase):

    def test_returns_count(self):
        ctx = _make_ctx(form_exports=[1, 2, 3], case_exports=[])
        assert calc_form_exports(ctx) == 3

    def test_returns_zero_when_empty(self):
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_form_exports(ctx) == 0


class TestCalcCaseExportsOnly(SimpleTestCase):

    def test_returns_count(self):
        ctx = _make_ctx(form_exports=[], case_exports=['a', 'b'])
        assert calc_case_exports_only(ctx) == 2

    def test_returns_zero_when_empty(self):
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_case_exports_only(ctx) == 0


class TestCalcScheduledExports(SimpleTestCase):

    def test_counts_daily_saved_exports(self):
        form_export = _make_export(is_daily_saved_export=True)
        case_export = _make_export(is_daily_saved_export=False)
        ctx = _make_ctx(form_exports=[form_export], case_exports=[case_export])
        assert calc_scheduled_exports(ctx) == 1

    def test_returns_zero_when_none_scheduled(self):
        export = _make_export(is_daily_saved_export=False)
        ctx = _make_ctx(form_exports=[export], case_exports=[])
        assert calc_scheduled_exports(ctx) == 0

    def test_counts_across_both_types(self):
        form_export = _make_export(is_daily_saved_export=True)
        case_export = _make_export(is_daily_saved_export=True)
        ctx = _make_ctx(
            form_exports=[form_export], case_exports=[case_export]
        )
        assert calc_scheduled_exports(ctx) == 2


class TestCalcHasExcelDashboard(SimpleTestCase):

    @patch('corehq.apps.reports.models.TableauVisualization.objects')
    def test_true_when_visualization_exists(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = True
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_has_excel_dashboard(ctx) is True
        mock_manager.filter.assert_called_once_with(domain='test')

    @patch('corehq.apps.reports.models.TableauVisualization.objects')
    def test_false_when_no_visualizations(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = False
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_has_excel_dashboard(ctx) is False


class TestCalcCaseListExplorerReports(SimpleTestCase):

    @patch('dimagi.utils.couch.cache.cache_core.cached_view')
    @patch('corehq.apps.saved_reports.models.ReportConfig.get_db')
    def test_counts_matching_slug(self, mock_get_db, mock_cached_view):
        mock_cached_view.return_value = [
            {'key': ['name slug', 'test', 'user1', 'case_list_explorer']},
            {'key': ['name slug', 'test', 'user2', 'case_list_explorer']},
            {'key': ['name slug', 'test', 'user1', 'other_report']},
        ]
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_case_list_explorer_reports(ctx) == 2

    @patch('dimagi.utils.couch.cache.cache_core.cached_view')
    @patch('corehq.apps.saved_reports.models.ReportConfig.get_db')
    def test_returns_zero_when_no_matches(self, mock_get_db, mock_cached_view):
        mock_cached_view.return_value = [
            {'key': ['name slug', 'test', 'user1', 'other_report']},
        ]
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_case_list_explorer_reports(ctx) == 0

    @patch('dimagi.utils.couch.cache.cache_core.cached_view')
    @patch('corehq.apps.saved_reports.models.ReportConfig.get_db')
    def test_returns_zero_when_empty(self, mock_get_db, mock_cached_view):
        mock_cached_view.return_value = []
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_case_list_explorer_reports(ctx) == 0


class TestCalcDetConfigs(SimpleTestCase):

    def test_counts_det_enabled(self):
        export1 = _make_export(show_det_config_download=True)
        export2 = _make_export(show_det_config_download=False)
        export3 = _make_export(show_det_config_download=True)
        ctx = _make_ctx(
            form_exports=[export1, export2], case_exports=[export3]
        )
        assert calc_det_configs(ctx) == 2

    def test_returns_zero_when_none_enabled(self):
        export = _make_export(show_det_config_download=False)
        ctx = _make_ctx(form_exports=[export], case_exports=[])
        assert calc_det_configs(ctx) == 0


class TestCalcOdataFeeds(SimpleTestCase):

    def test_counts_odata_configs(self):
        export1 = _make_export(is_odata_config=True)
        export2 = _make_export(is_odata_config=False)
        ctx = _make_ctx(form_exports=[export1], case_exports=[export2])
        assert calc_odata_feeds(ctx) == 1

    def test_returns_zero_when_none(self):
        export = _make_export(is_odata_config=False)
        ctx = _make_ctx(form_exports=[], case_exports=[export])
        assert calc_odata_feeds(ctx) == 0


class TestCalcLinkedDomains(SimpleTestCase):

    @patch('corehq.apps.linked_domain.models.DomainLink.objects')
    def test_counts_links(self, mock_manager):
        mock_manager.filter.return_value.count.return_value = 3
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_linked_domains(ctx) == 3

    @patch('corehq.apps.linked_domain.models.DomainLink.objects')
    def test_returns_zero_when_no_links(self, mock_manager):
        mock_manager.filter.return_value.count.return_value = 0
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_linked_domains(ctx) == 0


class TestCalcHasCaseDeduplication(SimpleTestCase):

    @patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.objects')
    def test_true_when_rule_exists(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = True
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_has_case_deduplication(ctx) is True

    @patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.objects')
    def test_false_when_no_rules(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = False
        ctx = _make_ctx(form_exports=[], case_exports=[])
        assert calc_has_case_deduplication(ctx) is False
