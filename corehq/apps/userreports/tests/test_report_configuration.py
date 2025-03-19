from corehq.apps.userreports.models import ReportConfiguration


def test_report_configuration_type_map():
    report = ReportConfiguration.wrap({
        'domain': 'test-domain',
        'config_id': None,
        'aggregation_columns': ['test-field'],
        'columns': [
            {
                'type': 'field',
                'column_id': 'test-column-0',
                'field': 'test-field',
                'aggregation': 'simple',
            },
            {
                'type': 'location',
                'column_id': 'test-column-1',
                'field': 'location-field',
            },
        ],
    })
    assert report.report_type == 'map'


def test_report_configuration_type_table():
    report = ReportConfiguration.wrap({
        'domain': 'test-domain',
        'config_id': None,
        'aggregation_columns': ['test-field'],
        'columns': [
            {
                'type': 'field',
                'column_id': 'test-column-0',
                'field': 'test-field',
                'aggregation': 'simple',
            },
        ],
    })
    assert report.report_type == 'table'


def test_report_configuration_type_list():
    report = ReportConfiguration.wrap({
        'domain': 'test-domain',
        'config_id': None,
        'aggregation_columns': ['doc_id'],
        'columns': [
            {
                'type': 'field',
                'column_id': 'test-column-0',
                'field': 'test-field',
                'aggregation': 'simple',
            },
        ],
    })
    assert report.report_type == 'list'
