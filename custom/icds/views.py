from __future__ import absolute_import, unicode_literals

from django.http import HttpResponse
from django.views import View

from corehq.apps.app_manager.dbaccessors import get_version_build_id, get_brief_apps_in_domain
from corehq.apps.domain.auth import get_username_and_password_from_request
from custom.icds.models import CCZHosting
from django.shortcuts import render, reverse


class CCZDownloadView(View):
    template_name = 'icds/file_hosting.html'

    def _prep_files_context(self, domain, app_versions):
        context = {}
        apps_in_domain = {a.id: a.name for a in get_brief_apps_in_domain(domain)}
        for app_id, details in app_versions.items():
            version = details['version']
            profile = details['profile']
            build_id = get_version_build_id(domain, app_id, version)
            context[apps_in_domain[app_id]] = reverse('view_app', args=[domain, app_id])
        return context

    def get(self, request, *args, **kwargs):
        identifier = kwargs.get('identifier')
        try:
            file_hosting = CCZHosting.objects.get(identifier=identifier)
        except CCZHosting.DoesNotExist:
            return HttpResponse(status=404)

        uname, passwd = get_username_and_password_from_request(request)
        if uname and passwd:
            if uname != file_hosting.username or passwd != file_hosting.get_password:
                return HttpResponse(status=401)
            context = {
                'identifier': identifier,
                'files': self._prep_files_context("mkangia-domain", file_hosting.app_versions)
            }
            return render(request, self.template_name, context)

        # Either they did not provide an authorization header or
        # something in the authorization attempt failed. Send a 401
        # back to them to ask them to authenticate.
        response = HttpResponse(status=401)
        response['WWW-Authenticate'] = 'Basic realm="%s"' % ''
        return response
