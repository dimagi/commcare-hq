from corehq.apps.adm.admin import ADMAdminInterface
from corehq.apps.adm.forms import ADMReportForm
from corehq.apps.adm.models import ADMReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn

class ADMReportEditInterface(ADMAdminInterface):
    name = "Default ADM Reports"
    description = "The report that shows up by default for each domain"
    slug = "default_adm_reports"

    adm_item_type = "ADM Report"
    property_class = ADMReport
    form_class = ADMReportForm

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Reporting Section"),
            DataTablesColumn("Slug"),
            DataTablesColumn("Domain"),
            DataTablesColumn("Report Name"),
            DataTablesColumn("Description"),
            DataTablesColumn("Columns"),
            DataTablesColumn("Key Type"),
            DataTablesColumn("Edit"),
        )

    @property
    def rows(self):
        rows = []
        key = ["defaults all slug"]
        data = self.property_class.view('adm/all_default_reports',
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key+[{}]
        ).all()
        for item in data:
            rows.append(item.as_row)
        return rows
