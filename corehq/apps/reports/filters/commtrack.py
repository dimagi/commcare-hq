from corehq.apps.reports.filters.base import CheckboxFilter
from django.utils.translation import ugettext_lazy


class AdvancedColumns(CheckboxFilter):
    label = ugettext_lazy("Show advanced columns")
    slug = "advanced_columns"
