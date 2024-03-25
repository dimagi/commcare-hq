from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext
from django.views.generic.base import View

from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import has_privilege

from corehq.apps.sso.utils.request_helpers import is_request_using_sso
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.modules import to_function

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.decorators import (
    cls_to_view,
    login_and_domain_required,
    track_domain_request,
)
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.reports.exceptions import BadRequestError
from corehq.util.quickcache import quickcache

from .lookup import ReportLookup

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)


def _(message):
    return gettext(message) if message is not None else None


class ReportDispatcher(View):
    """
        The ReportDispatcher is responsible for dispatching the correct reports or interfaces.

        To get a new report to show up, add it to one of the lists in `corehq.reports`

        It is intended that you subclass this dispatcher and specify the map_name settings attribute
        and a unique prefix (like project in project_report_dispatcher).

        It's also intended that you make the appropriate permissions checks in the permissions_check method
        and decorate the dispatch method with the appropriate permissions decorators.
        You may also override GenericReportView.allow_access in individual report classes

        ReportDispatcher expects to serve a report that is a subclass of GenericReportView.
    """
    prefix = None  # string. ex: project, custom, billing, interface, admin
    map_name = None

    def __init__(self, **kwargs):
        if not self.map_name or not isinstance(self.map_name, str):
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

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        """
            Override this method to check for appropriate permissions based on the report model
            and other arguments.
        """
        return True

    @classmethod
    def get_reports(cls, domain):
        lookup = ReportLookup(cls.map_name)
        return lookup.get_reports(domain)

    @classmethod
    def get_report(cls, domain, report_slug, config_id=None):
        """
        Returns the report class for `report_slug`, or None if no report is
        found.
        """
        # NOTE: This is duplicated logic also contained within ReportLookup. While
        # replacing this code with the lookup code does not cause issues for production,
        # it breaks the way some tests try to create mock versions of a dispatcher --
        # they override `get_reports` with a custom mapping, and then rely on this method
        # using the override. I think a deeper refactor will need to be done to handle this.

        # The reason this *should* be separated out into its own module is because
        # report name resolution is independent from handling dispatch logic;
        # code which doesn't care about dispatching urls or handling views should still be able
        # to resolve a slug to a report object
        for name, group in cls.get_reports(domain):
            for report in group:
                if report.slug == report_slug:
                    return report

        return None

    @classmethod
    @quickcache(['domain', 'report_slug'], timeout=300)
    def get_report_class_name(cls, domain, report_slug):
        report_cls = cls.get_report(domain, report_slug)
        return report_cls.__module__ + '.' + report_cls.__name__ if report_cls else ''

    def _redirect_slug(self, slug):
        return self.slug_aliases.get(slug) is not None

    def _slug_alias(self, slug):
        return self.slug_aliases.get(slug)

    @datespan_default
    def dispatch(self, request, domain=None, report_slug=None, render_as=None,
                 permissions_check=None, *args, **kwargs):
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

        class_name = self.get_report_class_name(domain, report_slug)
        report_class = to_function(class_name) if class_name else None

        permissions_check = permissions_check or self.permissions_check
        if (
            report_class
            and permissions_check(class_name, request, domain=domain)
            and self.toggles_enabled(report_class, request)
            and report_class.allow_access(request)
        ):
            try:
                report = report_class(request, domain=domain, **report_kwargs)
                report.rendered_as = render_as
                report.decorator_dispatcher(
                    request, domain=domain, report_slug=report_slug, *args, **kwargs
                )
                return getattr(report, '%s_response' % render_as)
            except BadRequestError as e:
                return HttpResponseBadRequest(e)
        else:
            raise Http404()

    @classmethod
    def as_view(cls, *args, **kwargs):
        view = super(ReportDispatcher, cls).as_view(*args, **kwargs)
        view.is_hq_report = True
        return view

    @staticmethod
    def toggles_enabled(report_class, request):
        if not getattr(report_class, 'toggles', ()):
            return True
        return all(toggle_enabled(request, toggle) for toggle in report_class.toggles)

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
    def navigation_sections(cls, request, domain):
        project = getattr(request, 'project', None)
        couch_user = getattr(request, 'couch_user', None)
        nav_context = []

        dispatcher = cls()  # uhoh

        reports = dispatcher.get_reports(domain)
        for section_name, report_group in reports:
            report_contexts = []
            for report in report_group:
                class_name = report.__module__ + '.' + report.__name__
                show_in_navigation = report.show_in_navigation(domain=domain, project=project, user=couch_user)
                show_in_dropdown = report.display_in_dropdown(domain=domain, project=project, user=couch_user)
                if (
                    dispatcher.permissions_check(class_name, request, domain=domain, is_navigation_check=True)
                    and cls.toggles_enabled(report, request)
                    and report.allow_access(request)
                    and (show_in_navigation or show_in_dropdown)
                ):
                    report_contexts.append({
                        'url': report.get_url(domain=domain, request=request, relative=True),
                        'description': _(report.description),
                        'icon': report.icon,
                        'title': _(report.name),
                        'subpages': report.get_subpages(),
                        'show_in_navigation': show_in_navigation,
                        'show_in_dropdown': show_in_dropdown,
                        'class_name': report.__name__,
                    })
            if report_contexts:
                if hasattr(section_name, '__call__'):
                    section_name = section_name(project, couch_user)
                nav_context.append((section_name, report_contexts))
        return nav_context

    @classmethod
    def url_pattern(cls):
        from django.urls import re_path as url
        return url(cls.pattern(), cls.as_view(), name=cls.name())


cls_to_view_login_and_domain = cls_to_view(additional_decorator=login_and_domain_required)


class ProjectReportDispatcher(ReportDispatcher):
    prefix = 'project_report'  # string. ex: project, custom, billing, interface, admin
    map_name = 'REPORTS'

    @property
    def slug_aliases(self):
        return {
            'daily_completions': 'daily_form_stats',
            'daily_submissions': 'daily_form_stats',
        }

    @cls_to_view_login_and_domain
    @track_domain_request(calculated_prop='cp_n_viewed_non_ucr_reports')
    def dispatch(self, request, *args, **kwargs):
        return super(ProjectReportDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        if domain is None:
            return False
        if not request.couch_user.is_active:
            return False
        return request.couch_user.can_view_report(domain, report)


class CustomProjectReportDispatcher(ProjectReportDispatcher):
    prefix = 'custom_project_report'
    map_name = 'CUSTOM_REPORTS'

    def dispatch(self, request, *args, **kwargs):
        render_as = kwargs.get('render_as')
        if not render_as == 'email':
            return self.dispatch_with_priv(request, *args, **kwargs)
        if not domain_has_privilege(request.domain, privileges.CUSTOM_REPORTS):
            raise PermissionDenied()
        return super(CustomProjectReportDispatcher, self).dispatch(request, *args, **kwargs)

    @method_decorator(requires_privilege_with_fallback(privileges.CUSTOM_REPORTS))
    def dispatch_with_priv(self, request, *args, **kwargs):
        return super(CustomProjectReportDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        if is_navigation_check and not has_privilege(request, privileges.CUSTOM_REPORTS):
            return False
        return super(CustomProjectReportDispatcher, self).permissions_check(report, request, domain)


class DomainReportDispatcher(ReportDispatcher):
    prefix = 'domain_report'
    map_name = 'DOMAIN_REPORTS'

    @cls_to_view_login_and_domain
    def dispatch(self, request, *args, **kwargs):
        return super(DomainReportDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        from corehq.motech.repeaters.views import DomainForwardingRepeatRecords
        if (report.endswith(DomainForwardingRepeatRecords.__name__)
                and not domain_has_privilege(domain, privileges.DATA_FORWARDING)):
            return False
        return super(DomainReportDispatcher, self).permissions_check(report, request, domain, is_navigation_check)


class AdminReportDispatcher(ReportDispatcher):
    prefix = 'admin_report'
    map_name = 'ADMIN_REPORTS'

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        return (
            hasattr(request, 'couch_user')
            and request.user.has_perm("is_superuser")
            and not is_request_using_sso(request)
        )


class UserManagementReportDispatcher(ReportDispatcher):
    prefix = 'user_management_report'
    map_name = 'USER_MANAGEMENT_REPORTS'

    @cls_to_view_login_and_domain
    def dispatch(self, request, *args, **kwargs):
        return super(UserManagementReportDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        from corehq.toggles import USER_HISTORY_REPORT
        return USER_HISTORY_REPORT.enabled_for_request(request)


class ReleaseManagementReportDispatcher(ReportDispatcher):
    prefix = 'release_management_report'
    map_name = 'RELEASE_MANAGEMENT_REPORTS'

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        from corehq.apps.linked_domain.util import can_user_access_linked_domains
        return can_user_access_linked_domains(request.couch_user, domain)
