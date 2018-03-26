from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.data_interfaces.interfaces import DataInterface
from django.utils.translation import ugettext_lazy


class ImportCases(DataInterface):
    name = ugettext_lazy("Import Cases from Excel")
    slug = "import_cases"
    description = ugettext_lazy("Import case data from an external Excel file")
    report_template_path = "case_importer/import_cases.html"
    gide_filters = True
    asynchronous = False
