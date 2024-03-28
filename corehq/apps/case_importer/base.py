from django.urls import reverse
from django.utils.translation import gettext_lazy, gettext_noop

from corehq.apps.case_importer.tracking.dbaccessors import (
    get_case_upload_record_count,
)
from corehq.apps.data_interfaces.interfaces import DataInterface
from corehq.apps.data_interfaces.views import DataInterfaceSection
from corehq.apps.locations.permissions import conditionally_location_safe
from corehq.privileges import LOCATION_SAFE_CASE_IMPORTS
from corehq.apps.accounting.utils import domain_has_privilege


def location_safe_case_imports_enabled(view_func, request, *args, **kwargs):
    return domain_has_privilege(kwargs['domain'], LOCATION_SAFE_CASE_IMPORTS)


@conditionally_location_safe(location_safe_case_imports_enabled)
class ImportCases(DataInterface):
    name = gettext_lazy("Import Cases from Excel")
    slug = "import_cases"
    report_template_path = "case_importer/bootstrap3/import_cases.html"
    hide_filters = True
    asynchronous = False

    @property
    def template_context(self, domain=None):
        return {
            'current_page': self.current_page_context(domain=self.domain),
            'section': self.section_context(),
            'record_count': get_case_upload_record_count(self.domain, self.request.couch_user),
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
                'title': gettext_noop('Case Options'),
                'urlname': 'excel_config'
            },
            {
                'title': gettext_noop('Match Excel Columns to Case Properties'),
                'urlname': 'excel_fields'
            }
        ]
