from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from corehq.apps.domain.decorators import (login_and_domain_required, require_superuser,
                                           login_required_late_eval_of_LOGIN_URL)
from django.core.urlresolvers import reverse
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


class BaseSettingsView(TemplateView):
    name = None  # name of the view used in urls
    page_name = None
    section_name = "Settings"
    template_name = "settings/base_template.html"

    @property
    def section_url(self):
        raise NotImplementedError

    @property
    def page_url(self):
        raise NotImplementedError

    @property
    def parent_pages(self):
        """
            Specify parent pages as a list of
            [{
                'name': <name>,
                'url: <url>,
            }]
        """
        return []

    @property
    @memoized
    def domain(self):
        return self.args[0] if len(self.args) > 0 else ""

    @property
    def main_context(self):
        """
            The context for the settings section.
        """
        return {
            'section': {
                'name': self.section_name,
                'url': self.section_url,
                },
            'settingspage': {
                'name': self.page_name,
                'url': self.page_url,
                'parents': self.parent_pages,
                },
            'domain': self.domain,
            }

    @property
    def page_context(self):
        """
            The Context for the settings page
        """
        raise NotImplementedError("This should return a dict.")

    def get_context_data(self, **kwargs):
        context = super(BaseSettingsView, self).get_context_data(**kwargs)
        context.update(self.main_context)
        context.update(self.page_context)
        return context

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseSettingsView, self).dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        """
            Returns a response with a template rendered with the given context.
        """
        return render(self.request, self.template_name, context)
