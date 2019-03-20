from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.case_importer.tracking.dbaccessors import get_case_upload_record_count
from corehq.apps.data_interfaces.interfaces import DataInterface
from corehq.apps.data_interfaces.views import DataInterfaceSection
from django.utils.translation import ugettext_noop as _
from django.urls import reverse
from django.utils.translation import ugettext_lazy


class ImportCases(DataInterface):
    name = ugettext_lazy("Import Cases from Excel")
    slug = "import_cases"
    report_template_path = "case_importer/import_cases.html"
    hide_filters = True
    asynchronous = False

    @property
    def template_context(self, domain=None):
        return {
            'current_page': self.current_page_context(domain=self.domain),
            'section': self.section_context(),
            'record_count': get_case_upload_record_count(self.domain),
        }

    @classmethod
    def section_context(cls, domain=None):
        return {
            'page_name': DataInterfaceSection.section_name,
            'url': reverse(DataInterfaceSection.urlname, args=[domain]),
        }

    @classmethod
    def current_page_context(cls, domain=None):
        return {
            'title': cls.name,
            'page_name': cls.name,
            'url': cls.get_url(domain=domain, relative=True),
        }

    @classmethod
    def get_subpages(cls):
        return [
            {
                'title': _('Case Options'),
                'urlname': 'excel_config'
            },
            {
                'title': _('Match Excel Columns to Case Properties'),
                'urlname': 'excel_fields'
            }
        ]
