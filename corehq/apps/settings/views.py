from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from corehq.apps.domain.decorators import (login_and_domain_required, require_superuser,
                                           login_required_late_eval_of_LOGIN_URL)
from django.core.urlresolvers import reverse
from corehq.apps.hqwebapp.utils import BaseSectionPageView
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_response

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_users(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_domain_settings(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("domain_forwarding", args=[domain]))

@login_required_late_eval_of_LOGIN_URL
def account_settings(request):
    # tabling this until HQ Announcements is flushed out.
    raise Http404

@require_superuser
def project_id_mapping(request, domain):
    from corehq.apps.users.models import CommCareUser
    from corehq.apps.groups.models import Group

    users = CommCareUser.by_domain(domain)
    groups = Group.by_domain(domain)

    return json_response({
        'users': dict([(user.raw_username, user.user_id) for user in users]),
        'groups': dict([(group.name, group.get_id) for group in groups]),
    })


class BaseSettingsView(BaseSectionPageView):
    section_name = "Settings"
    template_name = "settings/base_template.html"

    @property
    @memoized
    def domain(self):
        return self.args[0] if len(self.args) > 0 else ""

    @property
    def main_context(self):
        main_context = super(BaseSettingsView, self).main_context
        main_context.update({
            'domain': self.domain,
        })
        return main_context

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseSettingsView, self).dispatch(request, *args, **kwargs)

