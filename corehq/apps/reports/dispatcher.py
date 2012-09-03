from django.conf import settings
from django.http import HttpResponseNotFound, Http404
from django.views.generic.base import View
from corehq.apps.domain.decorators import login_and_domain_required, cls_login_and_domain_required, cls_to_view
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.modules import to_function
from django.utils.html import escape

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
        if not self.map_name or not isinstance(self.map_name, str):
            raise NotImplementedError("Class property 'map_name' must be a string, and not empty.")
        super(ReportDispatcher, self).__init__(**kwargs)

    _report_map = None
    @property
    def report_map(self):
        if self._report_map is None:
            self._report_map = getattr(settings, self.map_name, None)
        return self._report_map

    def validate_report_map(self, request, *args, **kwargs):
        return bool(isinstance(self.report_map, dict) and self.report_map)

    def permissions_check(self, report, request, *args, **kwargs):
        """
            Override this method to check for appropriate permissions based on the report model
            and other arguments.
        """
        return True

    def get_reports(self, request, *args, **kwargs):
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

    def dispatch(self, request, *args, **kwargs):
        if not self.validate_report_map(request, *args, **kwargs):
            return HttpResponseNotFound("Sorry, no reports have been configured yet.")

        current_slug = kwargs.get('report_slug')
        render_as = kwargs.get('render_as', 'view')

        reports = self.get_reports(request, *args, **kwargs)
        for key, report_model_paths in reports.items():
            for model_path in report_model_paths:
                report_class = to_function(model_path)
                if report_class.slug == current_slug:
                    report = report_class(request, *args, **kwargs)
                    if self.permissions_check(model_path, request, *args, **kwargs):
                        return getattr(report, '%s_response' % (render_as or 'view'))
        raise Http404

    @classmethod
    def name(cls):
        prefix = "%s" % cls.prefix if cls.prefix else ""
        return "%s_dispatcher" % prefix

    @classmethod
    def pattern(cls):
        return r'^((?P<render_as>[(json)|(async)|(filters)|(export)|(static)|(clear_cache)]+)/)?(?P<report_slug>[\w_]+)/$'

    @classmethod
    def allowed_renderings(cls):
        return ['json', 'async', 'filters', 'export', 'static', 'clear_cache']

    @classmethod
    def args_kwargs_from_context(cls, context):
        args = []
        kwargs = dict(report_slug=context.get('report',{}).get('slug',''))
        return args, kwargs

    @classmethod
    def report_navigation_list(cls, context):
        request = context.get('request')
        report_nav = list()
        dispatcher = cls()
        args, kwargs = dispatcher.args_kwargs_from_context(context)
        reports = dispatcher.get_reports(request, *args, **kwargs)
        current_slug = kwargs.get('report_slug')
        for key, models in reports.items():
            section = list()
            section_header = '<li class="nav-header">%s</li>' % escape(key)
            for model in models:
                if not dispatcher.permissions_check(model, request, *args, **kwargs):
                    continue
                report = to_function(model)
                if report.show_in_navigation(request, *args, **kwargs):
                    selected_report = bool(report.slug == current_slug)
                    section.append("""<li class="%(css_class)s"><a href="%(link)s" title="%(link_title)s">
                    %(icon)s%(title)s
                    </a></li>""" % dict(
                        css_class="active" if selected_report else "",
                        link=report.get_url(*args),
                        link_title=report.description or "",
                        icon='<i class="icon%s %s"></i> ' % ("-white" if selected_report else "", report.icon) if report.icon else "",
                        title=report.name
                    ))
            if section:
                report_nav.append(section_header)
                report_nav.extend(section)
        return "\n".join(report_nav)

cls_to_view_login_and_domain = cls_to_view(additional_decorator=login_and_domain_required)

class ProjectReportDispatcher(ReportDispatcher):
    prefix = 'project_report' # string. ex: project, custom, billing, interface, admin
    map_name = 'PROJECT_REPORT_MAP'

    @cls_to_view_login_and_domain
    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        return super(ProjectReportDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, *args, **kwargs):
        domain = kwargs.get('domain')
        if domain is None:
            domain = args[0]
        return request.couch_user.can_view_report(domain, report)

    @classmethod
    def args_kwargs_from_context(cls, context):
        args, kwargs = super(ProjectReportDispatcher, cls).args_kwargs_from_context(context)
        domain=context.get('domain')
        kwargs.update(
            domain=domain
        )
        args = [domain] + args
        return args, kwargs

class CustomProjectReportDispatcher(ProjectReportDispatcher):
    prefix = 'custom_project_report'
    map_name = 'CUSTOM_REPORT_MAP'

    def get_reports(self, request, *args, **kwargs):
        domain = request.domain
        return self.report_map.get(domain, {})
