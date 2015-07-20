from corehq.apps.reports.filters.base import BaseSingleOptionFilter, CheckboxFilter
from django.utils.translation import ugettext_lazy, ugettext_lazy


class SelectReportingType(BaseSingleOptionFilter):
    slug = "report_type"
    label = ugettext_lazy("Reporting data type")
    default_text = ugettext_lazy("Show aggregate data")

    @property
    def options(self):
        return [
            ("facilities", "Show facility level data"),
        ]


class AdvancedColumns(CheckboxFilter):
    label = ugettext_lazy("Show advanced columns")
    slug = "advanced_columns"
