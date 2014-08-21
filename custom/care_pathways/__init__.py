from django.utils.translation import ugettext_noop as _
from custom.care_pathways.reports.adoption_bar_char_report import AdoptionBarChartReport
from custom.care_pathways.reports.adoption_disaggregated_report import AdoptionDisaggregatedReport
from custom.care_pathways.reports.table_card_report import TableCardReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        AdoptionBarChartReport,
        AdoptionDisaggregatedReport,
        TableCardReport
    )),
)
