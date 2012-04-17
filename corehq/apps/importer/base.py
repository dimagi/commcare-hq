from corehq.apps.reports.custom import HQReport

class ExcelImporter(HQReport):
    name = "Import data from Excel"
    slug = "excel_import"
    description = "Import case data from an external Excel file"
    template_name = "excel_import.html"
    fields = []
    
    def calc(self):
        pass
