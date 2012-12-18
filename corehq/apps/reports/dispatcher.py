import datetime
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseNotFound, Http404, HttpResponseRedirect
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.views.generic.base import View
from corehq.apps.domain.decorators import login_and_domain_required, cls_login_and_domain_required, cls_to_view
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.modules import to_function
from django.utils.html import escape
from django.utils.translation import ugettext as _

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
        map_name = kwargs.get('map_name')
        if map_name:
            self.map_name = map_name
        if not self.map_name or not isinstance(self.map_name, str): # unicode?
            raise NotImplementedError("Class property 'map_name' must be a string, and not empty.")
        super(ReportDispatcher, self).__init__(**kwargs)

    @property
    def report_map(self):
        return getattr(settings, self.map_name, None)

    @property
    def slug_aliases(self):
        """
            For those times when you merge a report or delete it and still want to keep around the old link.
            Format like:
            { 'old_slug': 'new_slug' }
        """
        return {}

    def validate_report_map(self, request):
        return bool(isinstance(self.report_map, dict) and self.report_map)

    def permissions_check(self, report, request, domain=None):
        """
            Override this method to check for appropriate permissions based on the report model
            and other arguments.
        """
        return True

    def get_reports(self, domain=None):
        """
            Override this method as necessary for specially constructed report maps.
            For instance, custom reports are structured like:
            CUSTOM_REPORT_MAP = {
                "domain" : {
                    "Reporting Section Name": ['path.to.custom.report.ReportClass']
                }
            }
        """
        return self.report_map


    def get_report(self, domain, report_slug):
        """
        Returns the report class for a configured slug, or None if no
        report is found.
        """
        reports = self.get_reports(domain)
        for key, report_model_paths in reports.items():
            for model_path in report_model_paths:
                report_class = to_function(model_path)
                if report_class.slug == report_slug:
                    return report_class

        return None

    def _redirect_slug(self, slug):
        return self.slug_aliases.get(slug) is not None

    def _slug_alias(self, slug):
        return self.slug_aliases.get(slug)

    def dispatch(self, request, *args, **kwargs):
        if not self.validate_report_map(request):
            return HttpResponseNotFound("Sorry, no reports have been configured yet.")

        current_slug = kwargs.get('report_slug')
        render_as = kwargs.get('render_as') or 'view'
        domain = kwargs.get('domain') or getattr(request, 'domain', None)

        redirect_slug = self._redirect_slug(current_slug)

        if redirect_slug and render_as == 'email':
            # todo saved reports should probably change the slug to the redirected slug. this seems like a hack.
            current_slug = redirect_slug
        elif redirect_slug:
            new_args = [domain] if domain else []
            if render_as != 'view':
                new_args.append(render_as)
            new_args.append(redirect_slug)
            return HttpResponseRedirect(reverse(self.name(), args=new_args))

        report_kwargs = kwargs.copy()

        if domain:
            del report_kwargs['domain']
        del report_kwargs['report_slug']
        del report_kwargs['render_as']

        reports = self.get_reports(domain)

        for key, report_model_paths in reports.items():
            for model_path in report_model_paths:
                report_class = to_function(model_path)
                if report_class.slug == current_slug:
                    report = report_class(request, domain=domain, **report_kwargs)
                    report.rendered_as = render_as
                    if self.permissions_check(model_path, request, domain=domain):
                        return getattr(report, '%s_response' % render_as)
        raise Http404

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
        return ['json', 'async', 'filters', 'export', 'mobile', 'email', 'clear_cache', 'partial']

    @classmethod
    def report_navigation_list(cls, context):
        request = context.get('request')
        domain = context.get('domain') or getattr(request, 'domain', None)

        nav_context = []
        dispatcher = cls()
        current_slug = context.get('report',{}).get('slug','')

        reports = dispatcher.get_reports(domain)
        for key, models in reports.items():
            section = []
            for model in models:
                if not dispatcher.permissions_check(model, request, domain=domain):
                    continue
                report = to_function(model)
                if report.show_in_navigation(request, domain=domain):
                    if hasattr(report, 'override_navigation_list'):
                        section.extend(report.override_navigation_list(context))
                    else:
                        selected_report = bool(report.slug == current_slug)
                        section.append({
                            'is_report': True,
                            'is_active': selected_report,
                            'url': report.get_url(domain=domain),
                            'description': report.description,
                            'icon': report.icon,
                            'title': report.name,
                        })
            if section:
                nav_context.append({
                    'header': _(key),
                })
                nav_context.extend(section)
        return mark_safe(render_to_string("reports/standard/partials/navigation_items.html", {
            'navs': nav_context
        }))

    @classmethod
    def url_pattern(cls):
        from django.conf.urls.defaults import url
        return url(cls.pattern(), cls.as_view(), name=cls.name())

cls_to_view_login_and_domain = cls_to_view(additional_decorator=login_and_domain_required)

class ProjectReportDispatcher(ReportDispatcher):
    prefix = 'project_report' # string. ex: project, custom, billing, interface, admin
    map_name = 'PROJECT_REPORT_MAP'

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
    map_name = 'CUSTOM_REPORT_MAP'

    def get_reports(self, domain):
        return self.report_map.get(domain, {})
