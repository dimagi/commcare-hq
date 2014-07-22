from django.utils.translation import ugettext_noop as _
from custom.care_pathways.reports.adoption_bar_char_report import AdoptionBarChartReport

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        AdoptionBarChartReport,
    )),
)