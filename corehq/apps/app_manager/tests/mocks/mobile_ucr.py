from __future__ import absolute_import
from __future__ import unicode_literals
import mock
from couchdbkit import ResourceNotFound


def mock_report_configurations(report_configurations_by_id):
    return mock.patch('corehq.apps.app_manager.models.ReportModule.reports', property(
        lambda self: [report_configurations_by_id[r.report_id]
                      for r in self.report_configs]))


def mock_report_configuration_get(report_configurations_by_id):
    def get_report_config(_id, domain):
        try:
            return (report_configurations_by_id[_id], False)
        except KeyError:
            raise ResourceNotFound
    return mock.patch(
        'corehq.apps.app_manager.fixtures.mobile_ucr.get_report_config',
        get_report_config
    )


def mock_report_data(data):
    return mock.patch(
        'corehq.apps.userreports.reports.data_source.ConfigurableReportDataSource.get_data',
        lambda self: data)
