from corehq.apps.adm.admin import BaseADMAdminInterface
from corehq.apps.adm.admin.forms import ADMReportForm
from corehq.apps.adm.models import ADMReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn

class ADMReportAdminInterface(BaseADMAdminInterface):
    name = "Default ADM Reports"
    description = "The report that shows up by default for each domain"
    slug = "default_adm_reports"

    crud_item_type = "ADM Report"
    document_class = ADMReport
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
            DataTablesColumn("Sort By Default Column"),
            DataTablesColumn("Sort By Direction"),
            DataTablesColumn("Key Type"),
            DataTablesColumn("Edit"),
        )

    @property
    def rows(self):
        rows = []
        key = ["defaults all slug"]
        data = self.document_class.view('adm/all_default_reports',
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key+[{}]
        ).all()
        for item in data:
            rows.append(item.admin_crud.row)
        return rows
