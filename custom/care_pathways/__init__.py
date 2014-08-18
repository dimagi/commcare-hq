from django.utils.translation import ugettext_noop as _
from custom.care_pathways.reports.adoption_bar_char_report import AdoptionBarChartReport
from custom.care_pathways.reports.adoption_disaggregated_report import AdoptionDisaggregatedReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        AdoptionBarChartReport,
        AdoptionDisaggregatedReport
    )),
)



