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
        id=1,
        dashboard=dashboard,
        title='Map 1',
        case_type='type1',
        geo_case_property='property1',
        dashboard_tab=DashboardTab.CASES,
        display_order=1,
    )
    DashboardMap.objects.create(
        id=2,
        dashboard=dashboard,
        title='Map 2',
        case_type='type2',
        geo_case_property='property2',
        dashboard_tab=DashboardTab.CASES,
        display_order=3,
    )
    DashboardMap.objects.create(
        id=3,
        dashboard=dashboard,
        title='Map 3',
        case_type='type3',
        geo_case_property='property3',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=2,
    )
    DashboardMap.objects.create(
        id=4,
        dashboard=dashboard,
        title='Map 4',
        case_type='type4',
        geo_case_property='property4',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=4,
    )
    yield


@use(dashboard_fixture)
@fixture
def dashboard_reports():
    dashboard = dashboard_fixture()
    DashboardReport.objects.create(
        id=1,
        dashboard=dashboard,
        title='Report 1',
        report_configuration_id='report1',
        dashboard_tab=DashboardTab.CASES,
        display_order=2,
    )
    DashboardReport.objects.create(
        id=2,
        dashboard=dashboard,
        title='Report 2',
        report_configuration_id='report2',
        dashboard_tab=DashboardTab.CASES,
        display_order=4,
    )
    DashboardReport.objects.create(
        id=3,
        dashboard=dashboard,
        title='Report 3',
        report_configuration_id='report3',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=1,
    )
    DashboardReport.objects.create(
        id=4,
        dashboard=dashboard,
        title='Report 4',
        report_configuration_id='report4',
        dashboard_tab=DashboardTab.MOBILE_WORKERS,
        display_order=3,
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
        ('Map 2', 'cases', 3),
        ('Map 3', 'mobile_workers', 2),
        ('Map 4', 'mobile_workers', 4),
    ]


@use(dashboard_maps)
def test_dashboard_map_widget():
    dashboard = dashboard_fixture()
    widget = dashboard.maps.first().to_widget()
    assert widget == {
        'case_type': 'type1',
        'dashboard': {
            'domain': 'test-domain',
        },
        'description': None,
        'geo_case_property': 'property1',
        'id': 1,
        'title': 'Map 1',
        'widget_type': 'DashboardMap',
    }


@use(dashboard_reports)
def test_dashboard_report_ordering():
    dashboard = dashboard_fixture()
    report_ordering = [
        (report.title, report.dashboard_tab, report.display_order)
        for report in dashboard.reports.all()
    ]
    assert report_ordering == [
        ('Report 1', 'cases', 2),
        ('Report 2', 'cases', 4),
        ('Report 3', 'mobile_workers', 1),
        ('Report 4', 'mobile_workers', 3),
    ]


@use(dashboard_reports)
def test_dashboard_report_url():
    dashboard = dashboard_fixture()
    report = dashboard.reports.first()
    assert report.url == 'http://localhost:8000/a/test-domain/reports/configurable/report1/'


@use(dashboard_reports)
def test_dashboard_report_widget():
    dashboard = dashboard_fixture()
    widget = dashboard.reports.first().to_widget()
    assert widget == {
        'dashboard': {
            'domain': 'test-domain',
        },
        'description': None,
        'html_id_suffix': '-report1',
        'id': 1,
        'is_async': True,
        'report_configuration_id': 'report1',
        'slug': 'configurable',
        'title': 'Report 1',
        'url': 'http://localhost:8000/a/test-domain/reports/configurable/report1/',
        'widget_type': 'DashboardReport',
    }


@use(dashboard_maps, dashboard_reports)
def test_dashboard_map_report_widgets():
    dashboard = dashboard_fixture()
    widgets = dashboard.get_map_report_widgets_by_tab()
    assert widgets == {
        'cases': [
            {
                'case_type': 'type1',
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'geo_case_property': 'property1',
                'id': 1,
                'title': 'Map 1',
                'widget_type': 'DashboardMap',
            },
            {
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'html_id_suffix': '-report1',
                'id': 1,
                'is_async': True,
                'report_configuration_id': 'report1',
                'slug': 'configurable',
                'title': 'Report 1',
                'url': 'http://localhost:8000/a/test-domain/reports/configurable/report1/',
                'widget_type': 'DashboardReport',
            },
            {
                'case_type': 'type2',
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'geo_case_property': 'property2',
                'id': 2,
                'title': 'Map 2',
                'widget_type': 'DashboardMap',
            },
            {
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'html_id_suffix': '-report2',
                'id': 2,
                'is_async': True,
                'report_configuration_id': 'report2',
                'slug': 'configurable',
                'title': 'Report 2',
                'url': 'http://localhost:8000/a/test-domain/reports/configurable/report2/',
                'widget_type': 'DashboardReport',
            },
        ],
        'mobile_workers': [
            {
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'html_id_suffix': '-report3',
                'id': 3,
                'is_async': True,
                'report_configuration_id': 'report3',
                'slug': 'configurable',
                'title': 'Report 3',
                'url': 'http://localhost:8000/a/test-domain/reports/configurable/report3/',
                'widget_type': 'DashboardReport',
            },
            {
                'case_type': 'type3',
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'geo_case_property': 'property3',
                'id': 3,
                'title': 'Map 3',
                'widget_type': 'DashboardMap',
            },
            {
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'html_id_suffix': '-report4',
                'id': 4,
                'is_async': True,
                'report_configuration_id': 'report4',
                'slug': 'configurable',
                'title': 'Report 4',
                'url': 'http://localhost:8000/a/test-domain/reports/configurable/report4/',
                'widget_type': 'DashboardReport',
            },
            {
                'case_type': 'type4',
                'dashboard': {
                    'domain': 'test-domain',
                },
                'description': None,
                'geo_case_property': 'property4',
                'id': 4,
                'title': 'Map 4',
                'widget_type': 'DashboardMap',
            },
        ],
    }
