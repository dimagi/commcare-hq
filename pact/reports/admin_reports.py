from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport

class PactAdminReport(GenericTabularReport, CustomProjectReport):
    fields=['corehq.apps.reports.fields.DatespanField']
    name = "PACT Admin Reports"
    slug = "pactadmin"
    emailable =True
    exportable=True

    report_template_path = "pact/admin/pactadmin_reports.html"

    @property
    def report_context(self):
        ret = {"foo": "bar"}
        return ret



