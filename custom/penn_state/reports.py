from django.views.generic import TemplateView
from django.http import HttpResponse

from corehq.apps.reports.standard import CustomProjectReport

class LegacyReportView(CustomProjectReport):
    name = "Legacy Report"
    slug = "legacy"
    description = "Legacy Report for Pennsylvania State University"
    base_template_async = "penn_state/smiley_report.html"
    base_template = 'reports/standard/base_template.html'
    # base_template = 'reports/async/default.html'

    # def get(self, request, *args, **kwargs):
    #     print "**** Running report ****"
    #     return HttpResponse("Hi Mom!")

    def get_site_strategy(self):
        total = 11
        fraction = "4/5"
        return {
            'days': [
                ('Monday', 3),
                ('Tuesday', 2),
                ('Wednesday', 0),
                ('Thurday', 4),
                ('Friday', 2),
            ],
            'total': total,
            'fraction': fraction,
        }

    @property
    def report_context(self):
        return {
            'site_strategy': self.get_site_strategy()
        }