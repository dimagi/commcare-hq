from collections import namedtuple
from unittest.mock import patch

from corehq.apps.campaign.services import get_gauge_metric_value

Dashboard = namedtuple('Dashboard', ['domain'])
Gauge = namedtuple('Gauge', ['dashboard', 'case_type', 'metric', 'case_query'])


@patch('corehq.apps.campaign.services.CaseSearchES')
def test_get_number_of_cases_without_case_type(case_search_es_patch):
    case_search_es = case_search_es_patch.return_value
    dashboard = Dashboard(domain='test')

    gauge = Gauge(
        dashboard=dashboard,
        metric='number_of_cases',
        case_type='',
        case_query=None,
    )

    get_gauge_metric_value(gauge)

    case_search_es.domain.assert_called_once()
    case_search_es.domain.return_value.count.assert_called_once()


@patch('corehq.apps.campaign.services.CaseSearchES')
def test_get_number_of_cases_with_case_type(case_search_es_patch):
    case_search_es = case_search_es_patch.return_value
    dashboard = Dashboard(domain='test')

    gauge = Gauge(
        dashboard=dashboard,
        metric='number_of_cases',
        case_type='test_case_type',
        case_query=None,
    )

    get_gauge_metric_value(gauge)

    case_search_es.domain.assert_called_once()
    case_search_es.domain.return_value.case_type.assert_called_with('test_case_type')
    case_search_es.domain.return_value.case_type.return_value.count.assert_called_once()


@patch('corehq.apps.campaign.services.UserES')
def test_get_number_of_mobile_workers(user_es_patch):
    user_es = user_es_patch.return_value

    dashboard = Dashboard(domain='test')

    gauge = Gauge(
        dashboard=dashboard,
        metric='number_of_mobile_workers',
        case_type='',
        case_query=None,
    )

    get_gauge_metric_value(gauge)

    user_es.domain.assert_called_once()
    user_es.domain.return_value.mobile_users.assert_called_once()
    user_es.domain.return_value.mobile_users.return_value.count.assert_called_once()


@patch('corehq.apps.campaign.services.UserES')
def test_get_number_of_active_mobile_workers(user_es_patch):
    user_es = user_es_patch.return_value

    dashboard = Dashboard(domain='test')

    gauge = Gauge(
        dashboard=dashboard,
        metric='number_of_active_mobile_workers',
        case_type='',
        case_query=None,
    )

    get_gauge_metric_value(gauge)

    user_es.domain.assert_called_once()
    user_es.domain.return_value.mobile_users.assert_called_once()
    user_es.domain.return_value.mobile_users.return_value.is_active.assert_called_once()
    user_es.domain.return_value.mobile_users.return_value.is_active.return_value.count.assert_called_once()


@patch('corehq.apps.campaign.services.UserES')
def test_get_number_of_inactive_mobile_workers(user_es_patch):
    user_es = user_es_patch.return_value

    dashboard = Dashboard(domain='test')

    gauge = Gauge(
        dashboard=dashboard,
        metric='number_of_inactive_mobile_workers',
        case_type='',
        case_query=None,
    )

    get_gauge_metric_value(gauge)

    user_es.domain.assert_called_once()
    user_es.domain.return_value.mobile_users.assert_called_once()
    user_es.domain.return_value.mobile_users.return_value.is_active.assert_called_once_with(active=False)
    user_es.domain.return_value.mobile_users.return_value.is_active.return_value.count.assert_called_once()


@patch('corehq.apps.campaign.services.FormES')
def test_get_number_of_forms_submitted_by_mobile_workers(form_es_patch):
    form_es = form_es_patch.return_value

    dashboard = Dashboard(domain='test')

    gauge = Gauge(
        dashboard=dashboard,
        metric='number_of_forms_submitted_by_mobile_workers',
        case_type='',
        case_query=None,
    )

    get_gauge_metric_value(gauge)

    form_es.domain.assert_called_once()
    form_es.domain.return_value.user_type.assert_called_once_with('mobile')
    form_es.domain.return_value.user_type.return_value.count.assert_called_once()
