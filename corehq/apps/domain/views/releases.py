from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from django.utils.functional import cached_property
from django.shortcuts import redirect
from django.http.response import (
    HttpResponseForbidden,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.contrib import messages

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_brief_apps_in_domain,
    get_build_doc_by_version,
)
from corehq.apps.app_manager.decorators import require_can_edit_apps
from corehq.apps.app_manager.models import (
    AppReleaseByLocation,
    LatestEnabledBuildProfiles,
)
from corehq.apps.domain.forms import (
    ManageReleasesByLocationForm,
    ManageReleasesByAppProfileForm,
)
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.locations.models import SQLLocation


@method_decorator([toggles.MANAGE_RELEASES_PER_LOCATION.required_decorator(),
                   require_can_edit_apps], name='dispatch')
class ManageReleasesByLocation(BaseProjectSettingsView):
    template_name = 'domain/manage_releases_by_location.html'
    urlname = 'manage_releases_by_location'
    page_title = ugettext_lazy("Manage Releases By Location")

    @cached_property
    def form(self):
        return ManageReleasesByLocationForm(
            self.request,
            self.domain,
            data=self.request.POST if self.request.method == "POST" else None,
        )

    @staticmethod
    def _location_path_display(location_id):
        return SQLLocation.active_objects.get(location_id=location_id).get_path_display()

    @property
    def page_context(self):
        app_names = {app.id: app.name for app in get_brief_apps_in_domain(self.domain, include_remote=True)}
        q = AppReleaseByLocation.objects.filter(domain=self.domain)
        location_id_slug = self.request.GET.get('location_id')
        location_id = None
        if location_id_slug:
            location_id = self.form.extract_location_id(location_id_slug)
            if location_id:
                q = q.filter(location_id=location_id)
        if self.request.GET.get('app_id'):
            q = q.filter(app_id=self.request.GET.get('app_id'))
        version = self.request.GET.get('version')
        if version:
            q = q.filter(version=version)

        app_releases_by_location = [release.to_json() for release in q]
        for r in app_releases_by_location:
            r['app'] = app_names.get(r['app'], r['app'])
        return {
            'manage_releases_by_location_form': self.form,
            'app_releases_by_location': app_releases_by_location,
            'selected_build_details': ({'id': version, 'text': version} if version else None),
            'selected_location_details': ({'id': location_id_slug,
                                           'text': self._location_path_display(location_id)}
                                          if location_id else None),
        }

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            success, error_message = self.form.save()
            if success:
                return redirect(self.urlname, self.domain)
            else:
                messages.error(request, error_message)
                return self.get(request, *args, **kwargs)
        else:
            return self.get(request, *args, **kwargs)


@method_decorator([toggles.RELEASE_BUILDS_PER_PROFILE.required_decorator(),
                   require_can_edit_apps], name='dispatch')
class ManageReleasesByAppProfile(BaseProjectSettingsView):
    template_name = 'domain/manage_releases_by_app_profile.html'
    urlname = 'manage_releases_by_app_profile'
    page_title = ugettext_lazy("Manage Releases By App Profile")

    @cached_property
    def form(self):
        return ManageReleasesByAppProfileForm(
            self.request,
            self.domain,
            data=self.request.POST if self.request.method == "POST" else None,
        )

    @staticmethod
    def _get_initial_app_profile_details(domain, version, app_id, build_profile_id):
        # only need to set when performing search to populate with initial values in view
        if app_id and version:
            build_doc = get_build_doc_by_version(domain, app_id, version)
            if build_doc:
                return [{
                    'id': _id,
                    'text': details['name'],
                    'selected': build_profile_id == _id
                } for _id, details in build_doc['build_profiles'].items()]

    @property
    def page_context(self):
        app_names = {app.id: app.name for app in get_brief_apps_in_domain(self.domain, include_remote=True)}
        query = LatestEnabledBuildProfiles.objects.order_by('version')
        app_id = self.request.GET.get('app_id')
        if app_id:
            query = query.filter(app_id=app_id)
        else:
            query = query.filter(app_id__in=app_names.keys())
        version = self.request.GET.get('version')
        if version:
            query = query.filter(version=version)
        build_profile_id = self.request.GET.get('build_profile_id')
        if build_profile_id:
            query = query.filter(build_profile_id=build_profile_id)
        app_releases_by_app_profile = [release.to_json(app_names) for release in query]
        return {
            'manage_releases_by_app_profile_form': self.form,
            'app_releases_by_app_profile': app_releases_by_app_profile,
            'selected_build_details': ({'id': version, 'text': version} if version else None),
            'initial_app_profile_details': self._get_initial_app_profile_details(self.domain, version, app_id,
                                                                                 build_profile_id),
        }

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            success, error_message = self.form.save()
            if success:
                return redirect(self.urlname, self.domain)
            else:
                messages.error(request, error_message)
                return self.get(request, *args, **kwargs)
        else:
            return self.get(request, *args, **kwargs)


@require_can_edit_apps
@require_POST
def deactivate_release_restriction(request, domain, restriction_id):
    return _update_release_restriction(request, domain, restriction_id, active=False)


@require_can_edit_apps
@require_POST
def activate_release_restriction(request, domain, restriction_id):
    return _update_release_restriction(request, domain, restriction_id, active=True)


def _update_release_restriction(request, domain, restriction_id, active):
    if not toggles.MANAGE_RELEASES_PER_LOCATION.enabled_for_request(request):
        return HttpResponseForbidden()
    release = AppReleaseByLocation.objects.get(id=restriction_id, domain=domain)
    try:
        release.activate() if active else release.deactivate()
    except ValidationError as e:
        response_content = {
            'message': ','.join(e.messages)
        }
    else:
        response_content = {
            'id': restriction_id,
            'success': True,
            'activated_on': (datetime.strftime(release.activated_on, '%Y-%m-%d %H:%M:%S')
                             if release.activated_on else None),
            'deactivated_on': (datetime.strftime(release.deactivated_on, '%Y-%m-%d %H:%M:%S')
                               if release.deactivated_on else None),
        }
    return JsonResponse(data=response_content)


@require_can_edit_apps
@require_POST
def toggle_release_restriction_by_app_profile(request, domain, restriction_id):
    if not toggles.RELEASE_BUILDS_PER_PROFILE.enabled_for_request(request):
        return HttpResponseForbidden()
    release = LatestEnabledBuildProfiles.objects.get(id=restriction_id)
    if not release:
        return HttpResponseBadRequest()
    if request.POST.get('active') == 'false':
        return _update_release_restriction_by_app_profile(release, restriction_id, active=False)
    elif request.POST.get('active') == 'true':
        return _update_release_restriction_by_app_profile(release, restriction_id, active=True)


def _update_release_restriction_by_app_profile(release, restriction_id, active):
    try:
        release.activate() if active else release.deactivate()
    except ValidationError as e:
        response_content = {
            'message': ','.join(e.messages)
        }
    else:
        response_content = {
            'id': restriction_id,
            'success': True,
        }
    return JsonResponse(data=response_content)
