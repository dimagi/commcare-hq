from corehq.apps.data_interfaces.interfaces import DataInterface

class ImportCases(DataInterface):
    name = "Import Cases from Excel"
    slug = "import_cases"
    description = "Import case data from an external Excel file"
    report_template_path = "importer/import_cases.html"
    gide_filters = True
    asynchronous = False
