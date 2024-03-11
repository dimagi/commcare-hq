import pytz
import re
from collections import OrderedDict, defaultdict

from django.urls import re_path as url, include
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from django.urls import Resolver404
from django.utils.translation import gettext_lazy as _

from couchdbkit import ResourceConflict, ResourceNotFound

from dimagi.utils.web import json_response

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import (
    safe_cached_download,
    safe_download,
)
from corehq.apps.app_manager.exceptions import (
    AppManagerException,
    FormNotFoundException,
    ModuleNotFoundException,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tasks import autogenerate_build
from corehq.apps.app_manager.util import (
    add_odk_profile_after_build,
    get_latest_enabled_versions_per_profile,
)
from corehq.apps.app_manager.views.utils import get_langs
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqmedia.views import DownloadMultimediaZip
from corehq.toggles import toggles_enabled_for_request
from corehq.util.metrics import metrics_counter
from corehq.util.soft_assert import soft_assert
from corehq.util.timezones.conversions import ServerTime
from corehq.util.view_utils import set_file_download

BAD_BUILD_MESSAGE = _("Sorry: this build is invalid. Try deleting it and rebuilding. "
                      "If error persists, please report an issue")


def _get_build_profile_id(request):
    profile = request.GET.get('profile')
    if profile in request.app.build_profiles:
        return profile
    else:
        return None


@safe_download
def download_odk_profile(request, domain, app_id):
    """
    See ApplicationBase.create_profile

    """
    if not request.app.copy_of:
        username = request.GET.get('username', 'unknown user')
        autogenerate_build(request.app, username)
    else:
        request._always_allow_browser_caching = True
    profile = _get_build_profile_id(request)
    return HttpResponse(
        request.app.create_profile(is_odk=True, build_profile_id=profile),
        content_type="commcare/profile"
    )


@safe_download
def download_odk_media_profile(request, domain, app_id):
    if not request.app.copy_of:
        username = request.GET.get('username', 'unknown user')
        autogenerate_build(request.app, username)
    else:
        request._always_allow_browser_caching = True
    profile = _get_build_profile_id(request)
    return HttpResponse(
        request.app.create_profile(is_odk=True, with_media=True, build_profile_id=profile),
        content_type="commcare/profile"
    )


@safe_cached_download
def download_suite(request, domain, app_id):
    """
    See Application.create_suite

    """
    if not request.app.copy_of:
        request.app.set_form_versions()
    profile = _get_build_profile_id(request)
    return HttpResponse(
        request.app.create_suite(build_profile_id=profile)
    )


@safe_cached_download
def download_media_suite(request, domain, app_id):
    """
    See Application.create_media_suite

    """
    if not request.app.copy_of:
        request.app.set_media_versions()
    profile = _get_build_profile_id(request)
    return HttpResponse(
        request.app.create_media_suite(build_profile_id=profile)
    )


@safe_cached_download
def download_app_strings(request, domain, app_id, lang):
    """
    See Application.create_app_strings

    """
    profile = _get_build_profile_id(request)
    return HttpResponse(
        request.app.create_app_strings(lang, build_profile_id=profile),
        content_type='text/plain; charset=utf-8'
    )


@safe_cached_download
def download_xform(request, domain, app_id, module_id, form_id):
    """
    See FormBase.render_xform
    """
    profile = _get_build_profile_id(request)
    try:
        form = request.app.get_module(module_id).get_form(form_id)
        form = form.validate_form()
        return HttpResponse(form.render_xform(build_profile_id=profile))
    except (IndexError, ModuleNotFoundException):
        raise Http404()
    except AppManagerException:
        form_unique_id = request.app.get_module(module_id).get_form(form_id).unique_id
        response = validate_form_for_build(request, domain, app_id, form_unique_id, ajax=False)
        response.status_code = 404
        return response


class DownloadCCZ(DownloadMultimediaZip):
    name = 'download_ccz'
    compress_zip = True
    include_index_files = True

    @property
    def zip_name(self):
        return '{} - {} - v{}.ccz'.format(
            self.app.domain,
            self.app.name,
            self.app.version,
        )

    def check_before_zipping(self):
        if self.app.is_remote_app():
            self.include_multimedia_files = False
        super(DownloadCCZ, self).check_before_zipping()


@safe_cached_download
def download_file(request, domain, app_id, path):
    download_target_version = request.GET.get('download_target_version') == 'true'
    if download_target_version:
        parts = path.split('.')
        assert len(parts) == 2
        target = Application.get(app_id).commcare_flavor
        assert target != 'none'
        path = parts[0] + '-' + target + '.' + parts[1]

    content_type_map = {
        'ccpr': 'commcare/profile',
        'xml': 'application/xml',
        'txt': 'text/plain',
    }
    try:
        content_type = content_type_map[path.split('.')[-1]]
    except KeyError:
        content_type = None
    response = HttpResponse(content_type=content_type)

    if request.GET.get('download') == 'true':
        response['Content-Disposition'] = "attachment; filename={}".format(path)

    build_profile_id = _get_build_profile_id(request)
    build_profile_access = domain_has_privilege(domain, privileges.BUILD_PROFILES)
    if path in ('CommCare.jad', 'CommCare.jar'):
        set_file_download(response, path)
        full_path = path
    elif build_profile_id and build_profile_id in request.app.build_profiles and build_profile_access:
        full_path = 'files/%s/%s' % (build_profile_id, path)
    else:
        full_path = 'files/%s' % path

    def resolve_path(path):
        return url(r'^', include('corehq.apps.app_manager.download_urls')).resolve(path)

    def create_build_files(build_profile_id=None):
        request.app.create_build_files(build_profile_id=build_profile_id)
        request.app.save()

    def create_build_files_if_necessary_handling_conflicts(is_retry=False):
        try:
            try:
                # look for file guaranteed to exist if profile is created
                request.app.fetch_attachment('files/{id}/profile.xml'.format(id=build_profile_id))
            except ResourceNotFound:
                create_build_files(build_profile_id)
        except ResourceConflict:
            if is_retry:
                raise
            request.app = Application.get(request.app.get_id)
            create_build_files_if_necessary_handling_conflicts(True)

    # Todo; remove after https://dimagi-dev.atlassian.net/browse/ICDS-1483 is fixed
    extension = path.split(".")[-1]
    if extension not in content_type_map.keys():
        metrics_counter("commcare.invalid_download_requests",
            tags={"domain": domain, "extension": extension})
    try:
        assert request.app.copy_of
        # create build files for default profile if they were not created during initial build
        # or for language profiles for which build files have not been created yet
        try:
            payload = request.app.fetch_attachment(full_path)
        except ResourceNotFound:
            if not build_profile_id or (build_profile_id in request.app.build_profiles and build_profile_access):
                create_build_files_if_necessary_handling_conflicts()
            else:
                raise
            payload = request.app.fetch_attachment(full_path)
        response.write(payload)
        if path in ['profile.ccpr', 'media_profile.ccpr'] and request.app.last_released:
            last_released = request.app.last_released.replace(microsecond=0)    # mobile doesn't want microseconds
            last_released = ServerTime(last_released).user_time(pytz.UTC).done().isoformat()
            response['X-CommCareHQ-AppReleasedOn'] = last_released
        response['Content-Length'] = len(response.content)
        return response
    except (ResourceNotFound, AssertionError):
        if request.app.copy_of:
            if request.META.get('HTTP_USER_AGENT') == 'bitlybot':
                raise Http404()
            elif path == 'profile.ccpr':
                # legacy: should patch build to add odk profile
                # which wasn't made on build for a long time
                add_odk_profile_after_build(request.app)
                request.app.save()
                return download_file(request, domain, app_id, path)
            else:
                try:
                    resolve_path(path)
                except Resolver404:
                    # ok this was just a url that doesn't exist
                    pass
                else:
                    # this resource should exist but doesn't
                    _assert = soft_assert('@'.join(['jschweers', 'dimagi.com']))
                    _assert(False, 'Expected build resource %s not found' % path)
                raise Http404()
        try:
            callback, callback_args, callback_kwargs = resolve_path(path)
        except Resolver404:
            raise Http404()

        return callback(request, domain, app_id, *callback_args, **callback_kwargs)


@safe_download
def download_profile(request, domain, app_id):
    """
    See ApplicationBase.create_profile

    """
    if not request.app.copy_of:
        username = request.GET.get('username', 'unknown user')
        autogenerate_build(request.app, username)
    else:
        request._always_allow_browser_caching = True
    profile = _get_build_profile_id(request)
    return HttpResponse(
        request.app.create_profile(build_profile_id=profile)
    )


@safe_download
def download_media_profile(request, domain, app_id):
    if not request.app.copy_of:
        username = request.GET.get('username', 'unknown user')
        autogenerate_build(request.app, username)
    else:
        request._always_allow_browser_caching = True
    profile = _get_build_profile_id(request)
    return HttpResponse(
        request.app.create_profile(with_media=True, build_profile_id=profile)
    )


@safe_cached_download
def download_practice_user_restore(request, domain, app_id):
    if not request.app.copy_of:
        autogenerate_build(request.app, request.user.username)
    return HttpResponse(
        request.app.create_practice_user_restore()
    )


@login_and_domain_required
@safe_download
def download_index(request, domain, app_id):
    """
    A landing page, mostly for debugging, that has links the jad and jar as well as
    all the resource files that will end up zipped into the jar.

    """
    files = defaultdict(list)
    try:
        for file_ in source_files(request.app):
            form_filename = re.search(r'modules-(\d+)\/forms-(\d+)', file_[0])
            if form_filename:
                module_id, form_id = form_filename.groups()
                module = request.app.get_module(module_id)
                form = module.get_form(form_id)
                section_name = "m{} - {}".format(
                    module_id,
                    ", ".join(["({}) {}".format(lang, name)
                               for lang, name in module.name.items()])
                )
                files[section_name].append({
                    'name': file_[0],
                    'source': file_[1],
                    'readable_name': "f{} - {}".format(
                        form_id,
                        ", ".join(["({}) {}".format(lang, name)
                                   for lang, name in form.name.items()])
                    ),
                })
            else:
                files[None].append({
                    'name': file_[0],
                    'source': file_[1],
                    'readable_name': None,
                })
    except Exception:
        messages.error(
            request,
            _(
                "We were unable to get your files "
                "because your Application has errors. "
                "Please click <strong>Make New Version</strong> "
                "for feedback on how to fix these errors."
            ),
            extra_tags='html'
        )
    enabled_build_profiles = []
    latest_enabled_build_profiles = {}
    build_profiles = [{'id': build_profile_id, 'name': build_profile.name}
                      for build_profile_id, build_profile in request.app.build_profiles.items()]
    if request.app.is_released and toggles.RELEASE_BUILDS_PER_PROFILE.enabled(domain):
        latest_enabled_build_profiles = get_latest_enabled_versions_per_profile(request.app.copy_of)
        enabled_build_profiles = [_id for _id, version in latest_enabled_build_profiles.items()
                                  if version == request.app.version]

    return render(request, "app_manager/download_index.html", {
        'app': request.app,
        'files': OrderedDict(sorted(files.items(), key=lambda x: x[0] or '')),
        'build_profiles': build_profiles,
        'enabled_build_profiles': enabled_build_profiles,
        'latest_enabled_build_profiles': latest_enabled_build_profiles,
    })


def validate_form_for_build(request, domain, app_id, form_unique_id, ajax=True):
    app = get_app(domain, app_id)
    try:
        form = app.get_form(form_unique_id)
    except FormNotFoundException:
        # this can happen if you delete the form from another page
        raise Http404()
    errors = form.validate_for_build()
    lang, langs = get_langs(request, app)

    if ajax and "blank form" in [error.get('type') for error in errors]:
        response_html = ""
    else:
        response_html = render_to_string("app_manager/partials/build_errors.html", {
            'app': app,
            'build_errors': errors,
            'not_actual_build': True,
            'domain': domain,
            'langs': langs,
            'toggles': toggles_enabled_for_request(request),
        })

    if ajax:
        return json_response({
            'error_html': response_html,
        })
    else:
        return HttpResponse(response_html)


def download_index_files(app, build_profile_id=None):
    def needed_for_ccz(path):
        if profiles:
            return path.startswith(prefix) and path.split('/')[1] not in profiles
        else:
            return path.startswith(prefix)

    if app.copy_of:
        prefix = 'files/'
        if build_profile_id is not None:
            prefix += build_profile_id + '/'
        else:
            profiles = set(app.build_profiles)
        if not (prefix + 'profile.ccpr') in app.blobs:
            # profile hasnt been built yet
            app.create_build_files(build_profile_id=build_profile_id)
            app.save()
        files = [(path[len(prefix):], app.fetch_attachment(path))
                 for path in app.blobs if needed_for_ccz(path)]
    else:
        files = list(app.create_all_files().items())
    files = [
        (name, build_file if isinstance(build_file, str) else build_file.decode('utf-8'))
        for (name, build_file) in files
    ]
    return sorted(files)


def source_files(app):
    """
    Return the app's source files
    Return format is a list of tuples where the first item in the tuple is a
    file name and the second is the file contents.
    """
    if not app.copy_of:
        app.set_media_versions()
    return download_index_files(app)
