from django.views.generic import TemplateView
from django.http import HttpResponse

# from corehq.apps.reports.standard import CustomProjectReport

class LegacyReportView(TemplateView):
    name = "Legacy Report"
    slug = "legacy"
    description = "Legacy Report for Pennsylvania State University"
    template_name = "penn_state/smiley_report.html"
    show_in_navigation = True

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

    def get_context_data(self, **kwargs):
        print "******** Legacy Report!! ************"
        context = {
            'site_strategy': self.get_site_strategy()
        }
        context.update(kwargs)
        return context