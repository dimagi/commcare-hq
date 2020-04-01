import copy

from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from corehq.apps.domain.decorators import two_factor_exempt
from corehq.apps.domain.urls import PASSWORD_RESET_KWARGS, PASSWORD_RESET_DONE_KWARGS
from corehq.apps.hqwebapp import views as hqwebapp_views
from corehq.apps.locations.permissions import location_safe
from custom.icds_reports.dashboard_utils import get_dashboard_template_context
from custom.icds_reports.views import DASHBOARD_CHECKS
from custom.icds_reports.utils import get_latest_issue_tracker_build_id
from corehq.apps.cloudcare.utils import webapps_module
from corehq.apps.users.models import UserRole

from . import const


@xframe_options_exempt
def login(request, domain):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('cas_mobile_dashboard', args=[domain]))
    return hqwebapp_views.domain_login(
        request, domain,
        custom_template_name='icds_reports/mobile/mobile_login.html',
        extra_context={
            'domain': domain,
            'next': reverse('cas_mobile_dashboard', args=[domain]),
            'password_reset_url': reverse('cas_mobile_dashboard_password_reset', args=[domain]),
        }
    )


@xframe_options_exempt
@two_factor_exempt
def logout(req, domain):
    # override logout so you are redirected to the right login page afterwards
    return hqwebapp_views.logout(req, default_domain_redirect='cas_mobile_dashboard_login')


@xframe_options_exempt
def password_reset(request, domain):
    kwargs = copy.deepcopy(PASSWORD_RESET_KWARGS)
    kwargs['template_name'] = 'icds_reports/mobile/mobile_password_reset_form.html'
    # submit the form back to this view instead of the default
    kwargs['extra_context']['form_submit_url'] = reverse('cas_mobile_dashboard_password_reset', args=[domain])
    kwargs['extra_context']['login_url'] = reverse('cas_mobile_dashboard_login', args=[domain])
    # so that we can redirect to a custom "done" page
    kwargs['post_reset_redirect'] = reverse('cas_mobile_dashboard_password_reset_done', args=[domain])
    return auth_views.PasswordResetView.as_view(**kwargs)(request)


@xframe_options_exempt
def password_reset_done(request, domain):
    kwargs = copy.deepcopy(PASSWORD_RESET_DONE_KWARGS)
    kwargs['template_name'] = 'icds_reports/mobile/mobile_password_reset_done.html'
    kwargs['extra_context']['domain'] = domain
    return auth_views.PasswordResetDoneView.as_view(**kwargs)(request)


@location_safe
@method_decorator(DASHBOARD_CHECKS, name='dispatch')
@method_decorator(xframe_options_exempt, name='dispatch')
class MobileDashboardView(TemplateView):
    template_name = 'icds_reports/mobile/dashboard/mobile_dashboard.html'

    @property
    def domain(self):
        return self.kwargs['domain']

    def _has_helpdesk_role(self):
        user_roles = UserRole.by_domain(self.domain)
        helpdesk_roles_id = [
            role.get_id
            for role in user_roles
            if role.name in const.HELPDESK_ROLES
        ]
        domain_membership = self.request.couch_user.get_domain_membership(self.domain)
        return domain_membership.role_id in helpdesk_roles_id

    def get_context_data(self, **kwargs):
        kwargs.update(self.kwargs)
        kwargs.update(get_dashboard_template_context(self.domain, self.request.couch_user))
        kwargs['is_mobile'] = True
        if self.request.couch_user.is_commcare_user() and self._has_helpdesk_role():
            build_id = get_latest_issue_tracker_build_id()
            kwargs['report_an_issue_url'] = webapps_module(
                domain=self.domain,
                app_id=build_id,
                module_id=0,
            )
        return super().get_context_data(**kwargs)
