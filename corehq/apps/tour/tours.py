from corehq.apps.tour.models import GuidedTour
from corehq.apps.tour.views import EndTourView
from corehq.apps.userreports.util import has_report_builder_access
from corehq.util import reverse


class StaticGuidedTour(object):

    def __init__(self, slug, template):
        self.slug = slug
        self.template = template

    def get_tour_data(self):
        return {
            'slug': self.slug,
            'template': self.template,
            'endUrl': reverse(EndTourView.urlname, args=(self.slug,)),
        }

    def is_enabled(self, user):
        return not GuidedTour.has_seen_tour(user, self.slug)


class ReportBuilderExistenceTour(StaticGuidedTour):

    def get_tour_data(self, request, step):
        from corehq.apps.dashboard.views import DomainDashboardView
        from corehq.apps.reports.views import MySavedReportsView
        from corehq.apps.userreports.views import ReportBuilderPaywall
        data = super(ReportBuilderExistenceTour, self).get_tour_data()

        data.update({
            'step': step,
            'has_rb_access': has_report_builder_access(request),
            'dashboard_url': reverse(
                DomainDashboardView.urlname,
                args=[request.domain]
            ),
            'reports_home_url': reverse(
                MySavedReportsView.urlname,
                args=[request.domain],
                params={'tour': True}
            ),
            'report_builder_paywall_url': reverse(
                ReportBuilderPaywall.urlname,
                args=[request.domain],
                params={'tour': True}
            ),
        })
        return data


NEW_APP = StaticGuidedTour(
    'new_app', 'tour/config/new_app.html'
)
REPORT_BUILDER_EXISTENCE = ReportBuilderExistenceTour(
    'report_builder_existence', 'tour/config/report_builder_existence.html'
)
