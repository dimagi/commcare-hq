from corehq.apps.data_interfaces.interfaces import DataInterface
from django.utils.translation import ugettext_lazy


class ImportCases(DataInterface):
    name = ugettext_lazy("Import Cases from Excel")
    slug = "import_cases"
    description = ugettext_lazy("Import case data from an external Excel file")
    report_template_path = "importer/import_cases.html"
    gide_filters = True
    asynchronous = False
