from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division
import json
import uuid
from math import ceil

from django.db.models import Count
from django.http import HttpResponse, Http404
from django.http import HttpResponseRedirect
from django_prbac.utils import has_privilege
from django.views.generic import View
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError

from corehq.apps.app_manager.forms import PromptUpdateSettingsForm
from corehq.apps.app_manager.tasks import create_build_files_for_all_app_profiles
from corehq.apps.app_manager.util import get_and_assert_practice_user_in_domain
from django_prbac.decorators import requires_privilege
from django.contrib import messages
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy, ugettext as _
from django.views.decorators.cache import cache_control

import ghdiff
from couchdbkit import ResourceNotFound, NoResultFound
from dimagi.utils.web import json_response
from dimagi.utils.couch.bulk import get_docs
from phonelog.models import UserErrorEntry

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import track_built_app_on_hubspot
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_class
from corehq.apps.domain.decorators import login_or_api_key, track_domain_request
from corehq.apps.domain.views.base import LoginAndDomainMixin, DomainViewMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.locations.permissions import location_safe
from corehq.apps.sms.views import get_sms_autocomplete_context
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.apps.users.permissions import can_manage_releases
from corehq.util.timezones.utils import get_timezone_for_user

from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_app_cached,
    get_built_app_ids_for_app_id,
    get_current_app_version,
    get_latest_build_id,
    get_latest_build_version,
    get_latest_released_app_version,
)
from corehq.apps.app_manager.models import (
    BuildProfile,
    LatestEnabledBuildProfiles,
    AppReleaseByLocation,
)
from corehq.apps.users.models import CommCareUser
from corehq.util.datadog.gauges import datadog_bucket_timer
from corehq.util.view_utils import reverse
from corehq.apps.app_manager.decorators import (
    no_conflict_require_POST,
    require_can_edit_apps,
    require_deploy_apps,
)
from corehq.apps.app_manager.exceptions import ModuleIdMissingException, PracticeUserException
from corehq.apps.app_manager.models import Application, SavedAppBuild
from corehq.apps.app_manager.views.download import source_files
from corehq.apps.app_manager.views.settings import PromptSettingsUpdateView
from corehq.apps.app_manager.views.utils import back_to_main, get_langs
from corehq.apps.builds.models import CommCareBuildConfig
from corehq.apps.es.apps import AppES, build_comment, version
from corehq.apps.es import queries
from corehq.apps.users.models import CouchUser
import six


def _get_error_counts(domain, app_id, version_numbers):
    res = (UserErrorEntry.objects
           .filter(domain=domain,
                   app_id=app_id,
                   version_number__in=version_numbers)
           .values('version_number')
           .annotate(count=Count('pk')))
    return {r['version_number']: r['count'] for r in res}


@cache_control(no_cache=True, no_store=True)
@require_deploy_apps
def paginate_releases(request, domain, app_id):
    limit = request.GET.get('limit')
    only_show_released = json.loads(request.GET.get('only_show_released', 'false'))
    query = request.GET.get('query')
    page = int(request.GET.get('page', 1))
    page = max(page, 1)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    skip = (page - 1) * limit
    timezone = get_timezone_for_user(request.couch_user, domain)

    def _get_batch(start_build=None, skip=None):
        start_build = {} if start_build is None else start_build
        return Application.get_db().view('app_manager/saved_app',
            startkey=[domain, app_id, start_build],
            endkey=[domain, app_id],
            descending=True,
            limit=limit,
            skip=skip,
            wrapper=lambda x: (
                SavedAppBuild.wrap(x['value'], scrap_old_conventions=False)
                .releases_list_json(timezone)
            ),
        ).all()

    if not bool(only_show_released or query):
        # If user is limiting builds by released status or build comment, it's much
        # harder to be performant with couch. So if they're not doing so, take shortcuts.
        total_apps = len(get_built_app_ids_for_app_id(domain, app_id))
        saved_apps = _get_batch(skip=skip)
    else:
        app_es = (
            AppES()
            .start((page - 1) * limit)
            .size(limit)
            .sort('version', desc=True)
            .domain(domain)
            .is_build()
            .app_id(app_id)
        )
        if only_show_released:
            app_es = app_es.is_released()
        if query:
            app_es = app_es.add_query(build_comment(query), queries.SHOULD)
            try:
                app_es = app_es.add_query(version(int(query)), queries.SHOULD)
            except ValueError:
                pass

        results = app_es.exclude_source().run()
        total_apps = results.total
        app_ids = results.doc_ids
        apps = get_docs(Application.get_db(), app_ids)

        saved_apps = [
            SavedAppBuild.wrap(app, scrap_old_conventions=False).releases_list_json(timezone)
            for app in apps
        ]

    if toggles.APPLICATION_ERROR_REPORT.enabled(request.couch_user.username):
        versions = [app['version'] for app in saved_apps]
        num_errors_dict = _get_error_counts(domain, app_id, versions)
        for app in saved_apps:
            app['num_errors'] = num_errors_dict.get(app['version'], 0)

    num_pages = int(ceil(total_apps / limit))

    return json_response({
        'apps': saved_apps,
        'pagination': {
            'total': total_apps,
            'num_pages': num_pages,
            'current_page': page,
            'more': page * limit < total_apps,  # needed when select2 uses this endpoint
        }
    })


def get_releases_context(request, domain, app_id):
    app = get_app(domain, app_id)
    can_send_sms = domain_has_privilege(domain, privileges.OUTBOUND_SMS)
    build_profile_access = domain_has_privilege(domain, privileges.BUILD_PROFILES)
    prompt_settings_form = PromptUpdateSettingsForm.from_app(app, request_user=request.couch_user)

    context = {
        'release_manager': True,
        'can_send_sms': can_send_sms,
        'can_view_cloudcare': has_privilege(request, privileges.CLOUDCARE),
        'has_mobile_workers': get_doc_count_in_domain_by_class(domain, CommCareUser) > 0,
        'latest_released_version': get_latest_released_app_version(domain, app_id),
        'sms_contacts': (
            get_sms_autocomplete_context(request, domain)['sms_contacts']
            if can_send_sms else []
        ),
        'build_profile_access': build_profile_access,
        'application_profile_url': reverse(LanguageProfilesView.urlname, args=[domain, app_id]),
        'lastest_j2me_enabled_build': CommCareBuildConfig.latest_j2me_enabled_config().label,
        'latest_build_id': get_latest_build_id(domain, app_id),
        'prompt_settings_url': reverse(PromptSettingsUpdateView.urlname, args=[domain, app_id]),
        'prompt_settings_form': prompt_settings_form,
        'full_name': request.couch_user.full_name,
        'can_manage_releases': can_manage_releases(request.couch_user, request.domain, app_id)
    }
    if not app.is_remote_app():
        context.update({
            'enable_update_prompts': app.enable_update_prompts,
        })
        if len(app.modules) == 0:
            context.update({'intro_only': True})

        # Multimedia is not supported for remote applications at this time.
        try:
            multimedia_state = app.check_media_state()
            context.update({
                'multimedia_state': multimedia_state,
            })
        except ReportConfigurationNotFoundError:
            pass
    return context


@login_or_api_key
@location_safe
def current_app_version(request, domain, app_id):
    """
    Return current app version and the latest release
    """
    try:
        app_version = get_current_app_version(domain, app_id)
    except NoResultFound:
        # occurs when passed a build
        raise Http404
    latest_build_version = get_latest_build_version(domain, app_id)
    latest_released_version = get_latest_released_app_version(domain, app_id)
    return json_response({
        'currentVersion': app_version,
        'latestBuild': latest_build_version,
        'latestReleasedBuild': latest_released_version if latest_released_version else None,
    })


@no_conflict_require_POST
@require_can_edit_apps
@track_domain_request(calculated_prop='cp_n_click_app_deploy')
def release_build(request, domain, app_id, saved_app_id):
    is_released = request.POST.get('is_released') == 'true'
    if not is_released:
        if (LatestEnabledBuildProfiles.objects.filter(build_id=saved_app_id, active=True).exists() or
                AppReleaseByLocation.objects.filter(build_id=saved_app_id, active=True).exists()):
            return json_response({'error': _('Please disable any enabled profiles/location restriction '
                                             'to un-release this build.')})
    ajax = request.POST.get('ajax') == 'true'
    saved_app = get_app(domain, saved_app_id)
    if saved_app.copy_of != app_id:
        raise Http404
    saved_app.is_released = is_released
    saved_app.is_auto_generated = False
    saved_app.save(increment_version=False)
    from corehq.apps.app_manager.signals import app_post_release
    app_post_release.send(Application, application=saved_app)

    if is_released:
        if saved_app.build_profiles and domain_has_privilege(domain, privileges.BUILD_PROFILES):
            create_build_files_for_all_app_profiles.delay(domain, saved_app_id)
        _track_build_for_app_preview(domain, request.couch_user, app_id, 'User starred a build')

    if ajax:
        return json_response({
            'is_released': is_released,
            'latest_released_version': get_latest_released_app_version(domain, app_id)
        })
    else:
        return HttpResponseRedirect(reverse('release_manager', args=[domain, app_id]))


@no_conflict_require_POST
@require_can_edit_apps
def save_copy(request, domain, app_id):
    """
    Saves a copy of the app to a new doc.
    See VersionedDoc.save_copy

    """
    track_built_app_on_hubspot.delay(request.couch_user)
    comment = request.POST.get('comment')
    app = get_app(domain, app_id)
    try:
        errors = app.validate_app()
    except ModuleIdMissingException:
        # For apps (mainly Exchange apps) that lost unique_id attributes on Module
        app.ensure_module_unique_ids(should_save=True)
        errors = app.validate_app()

    if not errors:
        try:
            user_id = request.couch_user.get_id
            timer = datadog_bucket_timer('commcare.app_build.new_release', tags=[],
                                         timing_buckets=(1, 10, 30, 60, 120, 240))
            with timer:
                copy = app.make_build(
                    comment=comment,
                    user_id=user_id,
                )
                copy.save(increment_version=False)
            CouchUser.get(user_id).set_has_built_app()
        finally:
            # To make a RemoteApp always available for building
            if app.is_remote_app():
                app.save(increment_version=True)

        _track_build_for_app_preview(domain, request.couch_user, app_id, 'User created a build')

    else:
        copy = None
    copy = copy and SavedAppBuild.wrap(copy.to_json()).releases_list_json(
        get_timezone_for_user(request.couch_user, domain)
    )
    lang, langs = get_langs(request, app)

    return json_response({
        "saved_app": copy,
        "error_html": render_to_string("app_manager/partials/build_errors.html", {
            'request': request,
            'app': get_app(domain, app_id),
            'build_errors': errors,
            'domain': domain,
            'langs': langs,
            'lang': lang
        }),
    })


def _track_build_for_app_preview(domain, couch_user, app_id, message):
    track_workflow(couch_user.username, message, properties={
        'domain': domain,
        'app_id': app_id,
        'is_dimagi': couch_user.is_dimagi,
        'preview_app_enabled': True,
    })


@no_conflict_require_POST
@require_can_edit_apps
def revert_to_copy(request, domain, app_id):
    """
    Copies a saved doc back to the original.
    See VersionedDoc.revert_to_copy

    """
    app = get_app(domain, app_id)
    copy = get_app(domain, request.POST['build_id'])
    if copy.get_doc_type() == 'LinkedApplication' and app.get_doc_type() == 'Application':
        copy.convert_to_application()
    app = app.make_reversion_to_copy(copy)
    app.save()
    messages.success(
        request,
        _("Successfully reverted to version %(old_version)s, now at version %(new_version)s") % {
            'old_version': copy.version,
            'new_version': app.version,
        }
    )
    copy_build_comment_params = {
        "old_version": copy.version,
        "original_comment": copy.build_comment,
    }
    if copy.build_comment:
        copy_build_comment_template = _(
            "Reverted to version {old_version}\n\nPrevious build comments:\n{original_comment}")
    else:
        copy_build_comment_template = _("Reverted to version {old_version}")

    copy = app.make_build(
        comment=copy_build_comment_template.format(**copy_build_comment_params),
        user_id=request.couch_user.get_id,
    )
    copy.save(increment_version=False)
    return back_to_main(request, domain, app_id=app_id)


@no_conflict_require_POST
@require_can_edit_apps
def delete_copy(request, domain, app_id):
    """
    Deletes a saved copy permanently from the database.
    See VersionedDoc.delete_copy

    """
    app = get_app(domain, app_id)
    copy = get_app(domain, request.POST['saved_app'])
    app.delete_copy(copy)
    return json_response({})


def odk_install(request, domain, app_id, with_media=False):
    download_target_version = request.GET.get('download_target_version') == 'true'
    app = get_app(domain, app_id)
    qr_code_view = "odk_qr_code" if not with_media else "odk_media_qr_code"
    build_profile_id = request.GET.get('profile')
    profile_url = app.odk_profile_url if not with_media else app.odk_media_profile_url
    kwargs = []
    if build_profile_id is not None:
        kwargs.append('profile={profile}'.format(profile=build_profile_id))
    if download_target_version:
        kwargs.append('download_target_version=true')
    if kwargs:
        profile_url += '?' + '&'.join(kwargs)
    context = {
        "domain": domain,
        "app": app,
        "qr_code": reverse(qr_code_view,
                           args=[domain, app_id],
                           params={
                               'profile': build_profile_id,
                               'download_target_version': 'true' if download_target_version else 'false',
                           }),
        "profile_url": profile_url,
    }
    return render(request, "app_manager/odk_install.html", context)


def odk_qr_code(request, domain, app_id):
    profile = request.GET.get('profile')
    download_target_version = request.GET.get('download_target_version') == 'true'
    qr_code = get_app(domain, app_id).get_odk_qr_code(
        build_profile_id=profile, download_target_version=download_target_version
    )
    return HttpResponse(qr_code, content_type="image/png")


def odk_media_qr_code(request, domain, app_id):
    profile = request.GET.get('profile')
    download_target_version = request.GET.get('download_target_version') == 'true'
    qr_code = get_app(domain, app_id).get_odk_qr_code(
        with_media=True, build_profile_id=profile, download_target_version=download_target_version
    )
    return HttpResponse(qr_code, content_type="image/png")


def short_url(request, domain, app_id):
    build_profile_id = request.GET.get('profile')
    short_url = get_app(domain, app_id).get_short_url(build_profile_id=build_profile_id)
    return HttpResponse(short_url)


def short_odk_url(request, domain, app_id, with_media=False):
    build_profile_id = request.GET.get('profile')
    short_url = get_app(domain, app_id).get_short_odk_url(with_media=with_media, build_profile_id=build_profile_id)
    return HttpResponse(short_url)


@require_deploy_apps
def update_build_comment(request, domain, app_id):
    build_id = request.POST.get('build_id')
    try:
        build = SavedAppBuild.get(build_id)
    except ResourceNotFound:
        raise Http404()
    build.build_comment = request.POST.get('comment')
    build.is_auto_generated = False
    build.save()
    return json_response({'status': 'success'})


def _get_change_counts(html_diff):
    diff_lines = html_diff.splitlines()
    additions = sum(1 for line in diff_lines if line.startswith('<div class="insert">'))
    deletions = sum(1 for line in diff_lines if line.startswith('<div class="delete">'))
    return additions, deletions


def _get_file_pairs(first_app, second_app):
    """
    :param first_app:
    :param second_app:
    :return: A dictionary mapping file name to tuple where the first element is
     the corresponding file on the first app and the second is the corresponding
     file on the second app.
     "files" will be empty strings if the file does not exist on the app.
    """
    first_app_files = dict(source_files(first_app))
    second_app_files = dict(source_files(second_app))
    file_names = set(first_app_files.keys()) | set(second_app_files.keys())
    file_pairs = {
        n: (first_app_files.get(n, ""), second_app_files.get(n, ""))
        for n in file_names
    }
    return file_pairs


def _get_app_diffs(first_app, second_app):
    """
    Return a list of tuples. The first value in each tuple is a file name,
    the second value is an html snippet representing the diff of that file
    in the two given apps.
    """
    file_pairs = _get_file_pairs(first_app, second_app)
    diffs = []
    for name, files in six.iteritems(file_pairs):
        diff_html = ghdiff.diff(files[0], files[1], n=4, css=False)
        additions, deletions = _get_change_counts(diff_html)
        if additions == 0 and deletions == 0:
            diff_html = ""
        diffs.append({
            'name': name,
            'source': diff_html,
            'add_count': additions,
            'del_count': deletions,
        })
    return sorted(diffs, key=lambda f: f['name'])


class AppDiffView(LoginAndDomainMixin, BasePageView, DomainViewMixin):
    urlname = 'diff'
    page_title = ugettext_lazy("App diff")
    template_name = 'app_manager/app_diff.html'

    def dispatch(self, request, *args, **kwargs):
        return super(AppDiffView, self).dispatch(request, *args, **kwargs)

    @property
    def first_app_id(self):
        return self.kwargs["first_app_id"]

    @property
    def second_app_id(self):
        return self.kwargs["second_app_id"]

    @property
    def app_diffs(self):
        return _get_app_diffs(self.first_app, self.second_app)

    @property
    def main_context(self):
        context = super(AppDiffView, self).main_context
        context.update({
            'domain': self.domain,
        })
        return context

    @property
    def page_context(self):
        try:
            self.first_app = Application.get(self.first_app_id)
            self.second_app = Application.get(self.second_app_id)
        except (ResourceNotFound, KeyError):
            raise Http404()

        for app in (self.first_app, self.second_app):
            if not self.request.couch_user.is_member_of(app.domain):
                raise Http404()

        return {
            "app": self.first_app,
            "other_app": self.second_app,
            "files": {None: self.app_diffs},
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.first_app_id, self.second_app_id])


class LanguageProfilesView(View):
    urlname = 'build_profiles'

    @method_decorator(require_can_edit_apps)
    @method_decorator(requires_privilege(privileges.BUILD_PROFILES))
    def dispatch(self, request, *args, **kwargs):
        return super(LanguageProfilesView, self).dispatch(request, *args, **kwargs)

    def post(self, request, domain, app_id, *args, **kwargs):
        profiles = json.loads(request.body.decode('utf-8')).get('profiles')
        app = get_app(domain, app_id)
        build_profiles = {}
        if profiles:
            if app.is_remote_app() and len(profiles) > 1:
                # return bad request if they attempt to save more than one profile to a remote app
                return HttpResponse(status=400)
            for profile in profiles:
                id = profile.get('id')
                if not id:
                    id = uuid.uuid4().hex
                def practice_user_id():
                    if not app.enable_practice_users:
                        return ''
                    try:
                        practice_user_id = profile.get('practice_user_id')
                        if practice_user_id:
                            get_and_assert_practice_user_in_domain(practice_user_id, domain)
                        return practice_user_id
                    except PracticeUserException:
                        return HttpResponse(status=400)

                build_profiles[id] = BuildProfile(
                    langs=profile['langs'], name=profile['name'], practice_mobile_worker_id=practice_user_id())
        app.build_profiles = build_profiles
        app.save()
        return HttpResponse()

    def get(self, request, *args, **kwargs):
        return HttpResponse()


@require_can_edit_apps
def toggle_build_profile(request, domain, build_id, build_profile_id):
    build = get_app_cached(request.domain, build_id)
    status = request.GET.get('action') == 'enable'
    try:
        LatestEnabledBuildProfiles.update_status(build, build_profile_id, status)
    except ValidationError as e:
        messages.error(request, e)
    else:
        latest_enabled_build_profile = LatestEnabledBuildProfiles.for_app_and_profile(
            build.copy_of, build_profile_id)
        if latest_enabled_build_profile:
            messages.success(request, _("Latest version for profile {} is now {}").format(
                build.build_profiles[build_profile_id].name, latest_enabled_build_profile.version
            ))
        else:
            messages.success(request, _("Latest release now available for profile {}").format(
                build.build_profiles[build_profile_id].name
            ))
    return HttpResponseRedirect(reverse('download_index', args=[domain, build_id]))
