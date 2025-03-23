from unmagic import fixture, use  # https://github.com/dimagi/pytest-unmagic

from ..models import Dashboard, DashboardMap, DashboardReport, DashboardTab


@use('db')
@fixture
def dashboard_fixture():
    dashboard = Dashboard.objects.create(domain='test-domain')
    try:
        yield dashboard
    finally:
        dashboard.delete()


@use(dashboard_fixture)
@fixture
def dashboard_maps():
    dashboard = dashboard_fixture()
    DashboardMap.objects.create(
        dashboard=dashboard,
        title='Map 1',
        case_type='type1',
        geo_case_property='property1',
        dashboard_tab=DashboardTab.CASES,
        display_order=1,
    )
    DashboardMap.objects.create(
        dashboard=dashboard,
        title='Map 2',
        case_type='type2',
        geo_case_property='property2',
        dashboard_tab=DashboardTab.CASES,
        display_order=2,
    )
    DashboardMap.objects.create(
        dashboard=dashboard,
        title='Map 3',
        case_type='type3',
        geo_case_property='property3',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=1,
    )
    DashboardMap.objects.create(
        dashboard=dashboard,
        title='Map 4',
        case_type='type4',
        geo_case_property='property4',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=2,
    )
    yield


@use(dashboard_fixture)
@fixture
def dashboard_reports():
    dashboard = dashboard_fixture()
    DashboardReport.objects.create(
        dashboard=dashboard,
        title='Report 1',
        report_configuration_id='report1',
        dashboard_tab=DashboardTab.CASES,
        display_order=1,
    )
    DashboardReport.objects.create(
        dashboard=dashboard,
        title='Report 2',
        report_configuration_id='report2',
        dashboard_tab=DashboardTab.CASES,
        display_order=2,
    )
    DashboardReport.objects.create(
        dashboard=dashboard,
        title='Report 3',
        report_configuration_id='report3',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=1,
    )
    DashboardReport.objects.create(
        dashboard=dashboard,
        title='Report 4',
        report_configuration_id='report4',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=2,
    )
    yield


@use(dashboard_maps)
def test_dashboard_map_ordering():
    dashboard = dashboard_fixture()
    map_ordering = [
        (map.title, map.dashboard_tab, map.display_order)
        for map in dashboard.maps.all()
    ]
    assert map_ordering == [
        ('Map 1', 'cases', 1),
        ('Map 2', 'cases', 2),
        ('Map 3', 'mobile_workers', 1),
        ('Map 4', 'mobile_workers', 2),
    ]


@use(dashboard_reports)
def test_dashboard_report_ordering():
    dashboard = dashboard_fixture()
    report_ordering = [
        (report.title, report.dashboard_tab, report.display_order)
        for report in dashboard.reports.all()
    ]
    assert report_ordering == [
        ('Report 1', 'cases', 1),
        ('Report 2', 'cases', 2),
        ('Report 3', 'mobile_workers', 1),
        ('Report 4', 'mobile_workers', 2),
    ]


@use(dashboard_reports)
def test_dashboard_report_url():
    dashboard = dashboard_fixture()
    report = dashboard.reports.first()
    assert report.url == 'http://localhost:8000/a/test-domain/reports/configurable/report1/'
