from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.indicators.admin import BaseIndicatorAdminInterface
from corehq.apps.indicators.admin.forms import CombinedIndicatorForm
from corehq.apps.indicators.models import CombinedCouchViewIndicatorDefinition
from corehq.apps.reports.datatables import DataTablesColumn


class BaseDynamicIndicatorAdminInterface(BaseIndicatorAdminInterface):

    @property
    def headers(self):
        header = super(BaseDynamicIndicatorAdminInterface, self).headers
        header.insert_column(DataTablesColumn("Title"), -3)
        header.insert_column(DataTablesColumn("Description"), -3)
        return header


class CombinedIndicatorAdminInterface(BaseDynamicIndicatorAdminInterface):
    name = CombinedCouchViewIndicatorDefinition.get_nice_name()
    description = "Returns the ratio of two couch-based indicators (specified by their slugs)."
    slug = "dynamic_combined"
    document_class = CombinedCouchViewIndicatorDefinition
    form_class = CombinedIndicatorForm

    @property
    def headers(self):
        header = super(CombinedIndicatorAdminInterface, self).headers
        header.insert_column(DataTablesColumn("Numerator Slug"), -3)
        header.insert_column(DataTablesColumn("Denominator Slug"), -3)
        return header
