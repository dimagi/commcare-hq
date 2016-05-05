from corehq.apps.tour.models import GuidedTour
from corehq.apps.tour.views import EndTourView
from corehq.apps.userreports.util import has_report_builder_access, \
    has_report_builder_add_on_privilege
from corehq.util import reverse


def _implies(p, q):
    """
    Logical implication operator
    Return p => q
    """
    return (not p) or q

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


class ReportBuilderTour(StaticGuidedTour):
    """
    Base class for report builder tours
    """

    def get_tour_data(self, request, step):
        from corehq.apps.dashboard.views import DomainDashboardView
        from corehq.apps.reports.views import MySavedReportsView
        from corehq.apps.userreports.views import ReportBuilderPaywall
        data = super(ReportBuilderTour, self).get_tour_data()

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

    def should_show(self, request, step, tour_flag):
        """
        Return True if the tour should be shown for the given request.
        Note that this function assumes the request is for the page corresponding
        to the given step.
        :param request:
        :param step: Which step of the tour we're on
        :param tour_flag: If the page has a tour flag set
        """
        return self.is_enabled(request.user)


class ReportBuilderNoAccessTour(ReportBuilderTour):
    """
    A tour for users who don't yet have report builder access
    """
    def should_show(self, request, step, tour_flag):
        should_show = super(ReportBuilderNoAccessTour, self).should_show(request, step, tour_flag)
        return (
            should_show and
            not has_report_builder_access(request) and
            _implies(step > 0, tour_flag)  # All steps except the first require tour_flag
        )


class ReportBuilderAccessTour(ReportBuilderTour):
    """
    A tour for users who have add-on access to the report builder
    """
    def should_show(self, request, step, tour_flag):
        should_show = super(ReportBuilderAccessTour, self).should_show(request, step, tour_flag)
        return (
            should_show and
            has_report_builder_add_on_privilege(request)
        )


NEW_APP = StaticGuidedTour(
    'new_app', 'tour/config/new_app.html'
)
REPORT_BUILDER_NO_ACCESS = ReportBuilderNoAccessTour(
    'report_builder_no_access', 'tour/config/report_builder_no_access.html'
)
# Not calling this tour "REPORT_BUILDER" in case we actually make a tour of the
# report builder itself at some point.
REPORT_BUILDER_ACCESS = ReportBuilderAccessTour(
    'report_builder_access', 'tour/config/report_builder_access.html'
)
