from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse
from corehq.apps.crud.interface import BaseCRUDAdminInterface
from corehq.apps.indicators.dispatcher import IndicatorAdminInterfaceDispatcher
from corehq.apps.indicators.utils import get_namespaces
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from memoized import memoized


class BaseIndicatorAdminInterface(BaseCRUDAdminInterface):
    section_name = "Administer Indicators"
    base_template = 'reports/base_template.html'
    report_template_path = "indicators/interfaces/indicator_admin.html"
    dispatcher = IndicatorAdminInterfaceDispatcher

    crud_item_type = "Indicator Definition"

    @property
    def crud_item_type(self):
        return self.document_class.get_nice_name()

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Slug"),
            DataTablesColumn("Namespace"),
            DataTablesColumn("Version"),
            DataTablesColumn("Last Modified"),
            DataTablesColumn("Edit"),
        )

    @property
    def report_context(self):
        context = super(BaseIndicatorAdminInterface, self).report_context
        context.update({
            "bulk_add_url": self.bulk_add_url,
        })
        return context

    @property
    def bulk_add_url(self):
        return reverse("indicator_bulk_copy", args=[self.domain, self.document_class.__name__])

    @property
    def rows(self):
        rows = []
        for indicator in self.indicators:
            rows.append(indicator.admin_crud.row)
        return rows

    @property
    def crud_form_update_url(self):
        return "/a/%s/indicators/form/" % self.domain

    @property
    @memoized
    def indicator_namespaces(self):
        return get_namespaces(self.domain)

    @property
    @memoized
    def indicators(self):
        indicators = []
        for namespace in self.indicator_namespaces:
            indicators.extend(self.document_class.get_all_of_type(namespace, self.domain))
        return indicators

    @property
    def default_report_url(self):
        return reverse("default_indicator_admin", args=[self.domain])

    def validate_document_class(self):
        from corehq.apps.indicators.models import IndicatorDefinition
        if self.document_class is None or not issubclass(self.document_class, IndicatorDefinition):
            raise NotImplementedError("document_class must be an IndicatorDefinition and must not be None.")
