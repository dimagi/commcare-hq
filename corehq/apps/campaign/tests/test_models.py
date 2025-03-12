import pytest

from ..models import Dashboard, DashboardMap, DashboardReport, DashboardTab


@pytest.fixture
def dashboard():
    return Dashboard.objects.create(domain='test-domain')


@pytest.fixture
def dashboard_maps(dashboard):
    return [
        DashboardMap.objects.create(
            dashboard=dashboard,
            title='Map 1',
            case_type='type1',
            geo_case_property='property1',
            dashboard_tab=DashboardTab.CASES,
            display_order=1,
        ),
        DashboardMap.objects.create(
            dashboard=dashboard,
            title='Map 2',
            case_type='type2',
            geo_case_property='property2',
            dashboard_tab=DashboardTab.CASES,
            display_order=2,
        ),
        DashboardMap.objects.create(
            dashboard=dashboard,
            title='Map 3',
            case_type='type3',
            geo_case_property='property3',
            dashboard_tab=DashboardTab.MOBILE_WORKERS,
            display_order=1,
        ),
        DashboardMap.objects.create(
            dashboard=dashboard,
            title='Map 4',
            case_type='type4',
            geo_case_property='property4',
            dashboard_tab=DashboardTab.MOBILE_WORKERS,
            display_order=2,
        ),
    ]


@pytest.fixture
def dashboard_reports(dashboard):
    return [
        DashboardReport.objects.create(
            dashboard=dashboard,
            title='Report 1',
            report_configuration_id='report1',
            dashboard_tab=DashboardTab.CASES,
            display_order=1,
        ),
        DashboardReport.objects.create(
            dashboard=dashboard,
            title='Report 2',
            report_configuration_id='report2',
            dashboard_tab=DashboardTab.CASES,
            display_order=2,
        ),
        DashboardReport.objects.create(
            dashboard=dashboard,
            title='Report 3',
            report_configuration_id='report3',
            dashboard_tab=DashboardTab.MOBILE_WORKERS,
            display_order=1,
        ),
        DashboardReport.objects.create(
            dashboard=dashboard,
            title='Report 4',
            report_configuration_id='report4',
            dashboard_tab=DashboardTab.MOBILE_WORKERS,
            display_order=2,
        ),
    ]


@pytest.mark.django_db
def test_dashboard_map_ordering(
    dashboard,
    dashboard_maps,
):
    map_titles = [map.title for map in dashboard.maps.all()]
    assert map_titles == ['Map 1', 'Map 2', 'Map 3', 'Map 4']

    map_ordering = [
        (map.dashboard_tab, map.display_order)
        for map in dashboard.maps.all()
    ]
    assert map_ordering == [
        ('cases', 1),
        ('cases', 2),
        ('mobile_workers', 1),
        ('mobile_workers', 2),
    ]


@pytest.mark.django_db
def test_dashboard_report_ordering(
    dashboard,
    dashboard_reports,
):
    report_titles = [report.title for report in dashboard.reports.all()]
    assert report_titles == ['Report 1', 'Report 2', 'Report 3', 'Report 4']

    report_ordering = [
        (report.dashboard_tab, report.display_order)
        for report in dashboard.reports.all()
    ]
    assert report_ordering == [
        ('cases', 1),
        ('cases', 2),
        ('mobile_workers', 1),
        ('mobile_workers', 2),
    ]
