import mock


def mock_report_configurations(report_configurations_by_id):
    return mock.patch('corehq.apps.app_manager.models.ReportModule.reports', property(
        lambda self: [report_configurations_by_id[r.report_id]
                      for r in self.report_configs]))
