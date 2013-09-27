from django.views.generic import TemplateView
from django.http import HttpResponse

from corehq.apps.reports.standard import CustomProjectReport

domain = 'mikesproject'

class LegacyMixin(object):
    """
    Contains logic specific to this report.
    """

    def site_strategy(self):
        return [3, -1, 0, 4, 2]
    
    def site_game(self):
        return [2, 4, 3, 1, 0]
    
    def individual_strategy(self):
        return [2, 4, 0, 1, 3]
    
    def individual_game(self):
        return [1, 2, 4, 1, 0]


class LegacyReportView(LegacyMixin, CustomProjectReport):
    name = "Legacy Report"
    slug = "legacy"
    description = "Legacy Report for Pennsylvania State University"
    base_template = "penn_state/smiley_report.html"
    asynchronous = False

    # def get(self, request, *args, **kwargs):
    #     print "**** Running report ****"
    #     return HttpResponse("Hi Mom!")

    def context_for(self, days, icon):
        """
        days should be a 5 element array, with each element representing
        the number done that day.  -1 means that day was off.
        icon should be either "smiley" or "peace"
        """
        days_on = [day for day in days if day >= 0]
        days_used = [day for day in days if day > 0]
        return {
            'days': zip(
                ['Monday', 'Tuesday', 'Wednesday', 'Thurday', 'Friday'],
                days,
            ),
            'total': sum(days_used),
            'days_used': len(days_used),
            'days_on': len(days_on),
            'icon': icon,
        }

    @property
    def report_context(self):
        return {
            'site_strategy': self.context_for(
                self.site_strategy(), 'peace'),
            'site_game': self.context_for(
                self.site_game(), 'smiley'),
            'individual_strategy': self.context_for(
                self.individual_strategy(), 'peace'),
            'individual_game': self.context_for(
                self.individual_game(),'smiley'),
        }
        # return dict(
        #     (name, self.context_for(getattr(self, name)(), icon))
        #     for name, icon in [
        #         ('site_strategy', 'peace'),
        #         ('site_game', 'smiley'),
        #         ('individual_strategy', 'peace'),
        #         ('individual_game', 'smiley'),
        #     ]
        # )