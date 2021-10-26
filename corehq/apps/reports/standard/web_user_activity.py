import inspect

from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from corehq.apps.auditcare.models import NavigationEventAudit
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.view import ConfigurableReportView
from corehq.util.timezones.conversions import ServerTime
from corehq.util.view_utils import reverse
from corehq.toggles import WEB_USER_ACTIVITY_REPORT


class WebUserActivityReport(GetParamsMixin, DatespanMixin, GenericTabularReport, ProjectReport):
    slug = 'web_user_activity'
    name = ugettext_noop("Web User Activity")
    ajax_pagination = True
    sortable = False
    toggles = [WEB_USER_ACTIVITY_REPORT]

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleUsername',
    ]

    @classmethod
    def allow_access(cls, request):
        return (
            hasattr(request, 'couch_user')
            and request.couch_user.is_domain_admin(request.domain)
        )

    @classmethod
    def show_in_user_roles(cls, *args, **kwargs):
        return False

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Date")),
            DataTablesColumn(_("Report")),
        )

    @property
    def rows(self):
        events = self._get_queryset()[self.pagination.start:self.pagination.end]
        for event in events:
            yield [
                event.user,
                ServerTime(event.event_date).user_time(self.timezone).ui_string(),
                self._event_formatter.display(event),
            ]

    @property
    def total_records(self):
        return self._get_queryset().count()

    def _get_queryset(self):
        username = self.request.GET.get('username')
        return NavigationEventAudit.objects.filter(
            domain=self.domain,
            user=username,
            event_date__gt=self.datespan.startdate,
            event_date__lt=self.datespan.enddate_adjusted,
            view_fk__value__in=self._event_formatter.supported_views,
        ).order_by('-event_date').select_related('view_fk')

    @cached_property
    def _event_formatter(self):
        return EventFormatter(self.domain, self.request.project)


def for_view(view):
    def outer(fn):
        fn.view = view
        return fn
    return outer


class EventFormatter:
    """
    This class contains a series of methods for displaying navigation events.

    There's a method for each view, linked by the `for_view` decorator. Only
    views with methods here will appear in the report.
    """

    def __init__(self, domain, project):
        self.domain = domain
        self.project = project
        self._methods_by_view = {
            method.view: method
            for name, method in inspect.getmembers(self, predicate=inspect.ismethod)
            if getattr(method, 'view', None)
        }
        self.supported_views = list(self._methods_by_view.keys())

    def display(self, event):
        return self._methods_by_view[event.view](event)

    @for_view('corehq.apps.reports.dispatcher.ProjectReportDispatcher')
    def _get_report_display(self, event):
        slug = event.view_kwargs.get('report_slug')
        if slug and slug in self._report_displays_by_slug:
            return self._report_displays_by_slug[slug]
        return _("Unknown")

    @cached_property
    def _report_displays_by_slug(self):
        from corehq.reports import REPORTS
        return {
            report.slug: _link(_(report.name), report.get_url(self.domain))
            for tab in REPORTS(self.project) for report in tab[1]
        }

    @for_view('corehq.apps.userreports.reports.view.ConfigurableReportView')
    def _get_ucr_display(self, event):
        return self.ucr_displays_by_id[event.view_kwargs.get('subreport_slug')]

    @cached_property
    def ucr_displays_by_id(self):
        return {
            config._id: _link(
                config.title, reverse(ConfigurableReportView.slug, args=[self.domain, config._id])
            )
            for config in ReportConfiguration.by_domain(self.domain)
        }


def _link(name, url):
    return mark_safe(f'<a href="{url}">{name}</a>')
