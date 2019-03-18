from __future__ import absolute_import
from __future__ import unicode_literals

import json
from datetime import datetime
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from django.utils.functional import cached_property
from django.shortcuts import redirect
from django.http.response import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST

from corehq import toggles
from corehq.apps.app_manager.models import LatestEnabledAppReleases
from corehq.apps.domain.forms import ManageAppReleasesForm
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_select2_v4


@method_decorator([toggles.MANAGE_RELEASES_PER_LOCATION.required_decorator()], name='dispatch')
class ManageReleases(BaseProjectSettingsView):
    template_name = 'domain/manage_releases.html'
    urlname = 'manage_releases'
    page_title = ugettext_lazy("Manage Releases")

    @use_select2_v4
    def dispatch(self, request, *args, **kwargs):
        return super(ManageReleases, self).dispatch(request, *args, **kwargs)

    @cached_property
    def manage_releases_form(self):
        form = ManageAppReleasesForm(
            self.request,
            self.domain,
            data=self.request.POST if self.request.method == "POST" else None,
        )
        return form

    @property
    def page_context(self):
        return {
            'manage_releases_form': self.manage_releases_form,
            'enabled_app_releases': LatestEnabledAppReleases.to_json(
                self.domain, self.request.GET.get('location_id'), self.request.GET.get('app_id'),
                self.request.GET.get('version'))
        }

    def post(self, request, *args, **kwargs):
        if self.manage_releases_form.is_valid():
            self.manage_releases_form.save()
            return redirect(self.urlname, self.domain)
        else:
            return self.get(request, *args, **kwargs)


@login_and_domain_required
@require_POST
def deactivate_release_restriction(request, domain, restriction_id):
    if not toggles.MANAGE_RELEASES_PER_LOCATION.enabled_for_request(request):
        return HttpResponseForbidden()
    latest_enabled_app_release = LatestEnabledAppReleases.objects.get(id=restriction_id, domain=domain)
    latest_enabled_app_release.deactivate()
    response_content = {
        'id': restriction_id,
        'success': True,
        'activated_on': (datetime.strftime(latest_enabled_app_release.activated_on, '%Y-%m-%d %H:%M:%S')
                         if latest_enabled_app_release.activated_on else None),
        'deactivated_on': (datetime.strftime(latest_enabled_app_release.deactivated_on, '%Y-%m-%d %H:%M:%S')
                           if latest_enabled_app_release.deactivated_on else None),
    }
    return HttpResponse(json.dumps(response_content), content_type='application/json')


@login_and_domain_required
@require_POST
def activate_release_restriction(request, domain, restriction_id):
    if not toggles.MANAGE_RELEASES_PER_LOCATION.enabled_for_request(request):
        return HttpResponseForbidden()
    latest_enabled_app_release = LatestEnabledAppReleases.objects.get(id=restriction_id, domain=domain)
    latest_enabled_app_release.activate()
    response_content = {
        'id': restriction_id,
        'success': True,
        'activated_on': (datetime.strftime(latest_enabled_app_release.activated_on, '%Y-%m-%d %H:%M:%S')
                         if latest_enabled_app_release.activated_on else None),
        'deactivated_on': (datetime.strftime(latest_enabled_app_release.deactivated_on, '%Y-%m-%d %H:%M:%S')
                           if latest_enabled_app_release.deactivated_on else None),
    }
    return HttpResponse(json.dumps(response_content), content_type='application/json')
