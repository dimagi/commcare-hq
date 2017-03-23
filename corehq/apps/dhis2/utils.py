from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.util.couch import get_document_or_not_found


def get_ucr_data(domain_name, ucr_id):
    report_config = get_document_or_not_found(ReportConfiguration, domain_name, ucr_id)
    data_source = ReportFactory.from_spec(report_config)
    return data_source.get_data()
