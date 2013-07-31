from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponseBadRequest
from django.views.generic.base import View
from corehq.apps.domain.decorators import login_and_domain_required, cls_to_view
from dimagi.utils.decorators.datespan import datespan_in_request

from corehq.apps.domain.models import Domain
from corehq.apps.reports.exceptions import BadRequestError

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

class ReportDispatcher(View):
    """
        The ReportDispatcher is responsible for dispatching the correct reports or interfaces
        based on a REPORT_MAP or INTERFACE_MAP specified in settings.

        The mapping should be structured as follows.

        REPORT_MAP = {
            "Section Name" : [
                'app.path.to.report.ReportClass',
            ]
        }

        It is intended that you subclass this dispatcher and specify the map_name settings attribute
        and a unique prefix (like project in project_report_dispatcher).

        It's also intended that you make the appropriate permissions checks in the permissions_check method
        and decorate the dispatch method with the appropriate permissions decorators.

        ReportDispatcher expects to serve a report that is a subclass of GenericReportView.
    """
    prefix = None # string. ex: project, custom, billing, interface, admin
    map_name = None

    def __init__(self, **kwargs):
        if not self.map_name or not isinstance(self.map_name, basestring): # unicode?
            raise NotImplementedError("Class property 'map_name' must be a string, and not empty.")
        super(ReportDispatcher, self).__init__(**kwargs)

    @property
    def slug_aliases(self):
        """
            For those times when you merge a report or delete it and still want to keep around the old link.
            Format like:
            { 'old_slug': 'new_slug' }
        """
        return {}

    def permissions_check(self, report, request, domain=None):
        """
            Override this method to check for appropriate permissions based on the report model
            and other arguments.
        """
        return True

    def get_reports(self, domain=None):
        attr_name = self.map_name
        import corehq
        domain_module = Domain.get_module_by_name(domain)
        if domain:
            project = Domain.get_by_name(domain)
        else:
            project = None

        def process(reports):
            if project and callable(reports):
                reports = reports(project)
            return tuple(reports)

        corehq_reports = process(getattr(corehq, attr_name, ()))
        custom_reports = process(getattr(domain_module, attr_name, ()))

        return corehq_reports + custom_reports

    def get_reports_dict(self, domain=None):
        return dict((report.slug, report)
                    for name, group in self.get_reports(domain)
                    for report in group)

    def get_report(self, domain, report_slug):
        """
        Returns the report class for `report_slug`, or None if no report is
        found.

        """
        return self.get_reports_dict(domain).get(report_slug, None)

    def _redirect_slug(self, slug):
        return self.slug_aliases.get(slug) is not None

    def _slug_alias(self, slug):
        return self.slug_aliases.get(slug)

    def dispatch(self, request, domain=None, report_slug=None, render_as=None,
                 *args, **kwargs):
        render_as = render_as or 'view'
        domain = domain or getattr(request, 'domain', None)

        redirect_slug = self._redirect_slug(report_slug)

        if redirect_slug and render_as == 'email':
            # todo saved reports should probably change the slug to the redirected slug. this seems like a hack.
            raise Http404
        elif redirect_slug:
            new_args = [domain] if domain else []
            if render_as != 'view':
                new_args.append(render_as)
            new_args.append(redirect_slug)
            return HttpResponseRedirect(reverse(self.name(), args=new_args))

        report_kwargs = kwargs.copy()

        cls = self.get_report(domain, report_slug)
        class_name = cls.__module__ + '.' + cls.__name__ if cls else ''

        if cls and self.permissions_check(class_name, request, domain=domain):
            report = cls(request, domain=domain, **report_kwargs)
            report.rendered_as = render_as
            try:
                return getattr(report, '%s_response' % render_as)
            except BadRequestError, e:
                return HttpResponseBadRequest(e)
        else:
            raise Http404()

    @classmethod
    def name(cls):
        prefix = "%s" % cls.prefix if cls.prefix else ""
        return "%s_dispatcher" % prefix

    @classmethod
    def _rendering_pattern(cls):
        return "(?P<render_as>[{renderings}]+)".format(
            renderings="|".join("(%s)" % r for r in cls.allowed_renderings())
        )

    @classmethod
    def pattern(cls):
        return r'^({renderings}/)?(?P<report_slug>[\w_]+)/$'.format(renderings=cls._rendering_pattern())

    @classmethod
    def allowed_renderings(cls):
        return ['json', 'async', 'filters', 'export', 'mobile', 'email', 'partial', 'print']

    @classmethod
    def navigation_sections(cls, context):
        request = context.get('request')
        domain = context.get('domain') or getattr(request, 'domain', None)
        project = getattr(request, 'project', None)
        couch_user = getattr(request, 'couch_user', None)
        
        nav_context = []

        dispatcher = cls()  # uhoh
        current_slug = context.get('report',{}).get('slug','')

        reports = dispatcher.get_reports(domain)
        for section_name, report_group in reports:
            report_contexts = []
            for report in report_group:
                class_name = report.__module__ + '.' + report.__name__
                if not dispatcher.permissions_check(class_name, request, domain=domain):
                    continue
                if report.show_in_navigation(
                        domain=domain, project=project, user=couch_user):
                    if hasattr(report, 'override_navigation_list'):
                        report_contexts.extend(report.override_navigation_list(context))
                    else:
                        report_contexts.append({
                            'is_active': report.slug == current_slug,
                            'url': report.get_url(domain=domain),
                            'description': report.description,
                            'icon': report.icon,
                            'title': report.name,
                        })
            if report_contexts:
                if hasattr(section_name, '__call__'):
                    section_name = section_name(project, couch_user)
                nav_context.append((section_name, report_contexts))
        return nav_context

    @classmethod
    def url_pattern(cls):
        from django.conf.urls.defaults import url
        return url(cls.pattern(), cls.as_view(), name=cls.name())

cls_to_view_login_and_domain = cls_to_view(additional_decorator=login_and_domain_required)

class ProjectReportDispatcher(ReportDispatcher):
    prefix = 'project_report' # string. ex: project, custom, billing, interface, admin
    map_name = 'REPORTS'

    @property
    def slug_aliases(self):
        return {
            'daily_completions': 'daily_form_stats',
            'daily_submissions': 'daily_form_stats',
            'submit_time_punchcard': 'worker_activity_times',
        }

    @cls_to_view_login_and_domain
    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        return super(ProjectReportDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None):
        if domain is None:
            return False
        return request.couch_user.can_view_report(domain, report)

class CustomProjectReportDispatcher(ProjectReportDispatcher):
    prefix = 'custom_project_report'
    map_name = 'CUSTOM_REPORTS'

class BasicReportDispatcher(ReportDispatcher):
    prefix = 'basic_report'
    map_name = 'BASIC_REPORTS'

class AdminReportDispatcher(ReportDispatcher):
    prefix = 'admin_report'
    map_name = 'ADMIN_REPORTS'

    def permissions_check(self, report, request, domain=None):
        return hasattr(request, 'couch_user') and request.user.has_perm("is_superuser")
