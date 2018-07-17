from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.data_interfaces.interfaces import DataInterface
from corehq.apps.data_interfaces.views import DataInterfaceSection
from django.urls import reverse
from django.utils.translation import ugettext_lazy


class ImportCases(DataInterface):
    name = ugettext_lazy("Import Cases from Excel")
    slug = "import_cases"
    report_template_path = "case_importer/import_cases.html"
    hide_filters = True
    asynchronous = False

    @property
    def template_context(self):
        return {
            'current_page': {
                'title': self.name,
                'page_name': self.name,
            },
            'section': {
                'page_name': DataInterfaceSection.section_name,
                'url': reverse(DataInterfaceSection.urlname, args=[self.domain]),
            },
        }
