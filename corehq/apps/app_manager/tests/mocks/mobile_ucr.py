import mock


def mock_report_configurations(report_configurations_by_id):
    return mock.patch('corehq.apps.app_manager.models.ReportModule.reports', property(
        lambda self: [report_configurations_by_id[r.report_id]
                      for r in self.report_configs]))


def mock_report_configuration_get(report_configurations_by_id):
    return mock.patch(
        'corehq.apps.userreports.models.ReportConfiguration.get',
        classmethod(lambda self, _id: report_configurations_by_id[_id]))


def mock_report_data(data):
    return mock.patch(
        'corehq.apps.userreports.reports.data_source.ConfigurableReportDataSource.get_data',
        lambda self: data)
