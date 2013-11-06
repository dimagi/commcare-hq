from corehq.apps.data_interfaces.interfaces import DataInterface
from django.utils.translation import ugettext as _

class ImportCases(DataInterface):
    name = _("Import Cases from Excel")
    slug = "import_cases"
    description = _("Import case data from an external Excel file")
    report_template_path = "importer/import_cases.html"
    gide_filters = True
    asynchronous = False
