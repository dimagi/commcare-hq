import json

from django.template.loader import render_to_string
from django.views.decorators.cache import cache_control
from django.http import HttpResponse, Http404
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.shortcuts import render
from couchdbkit.resource import ResourceNotFound
from django.contrib import messages
from corehq.apps.app_manager.views.apps import get_apps_base_context

from corehq.apps.app_manager.views.utils import back_to_main, encode_if_unicode, \
    get_langs
from corehq import toggles, privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import track_built_app_on_hubspot
from corehq.apps.app_manager.exceptions import (
    ModuleIdMissingException,
)
from corehq.apps.sms.views import get_sms_autocomplete_context
from dimagi.utils.couch.database import get_db
from dimagi.utils.web import json_response
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.apps.domain.decorators import (
    login_and_domain_required,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    Application,
    SavedAppBuild,
)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps


@cache_control(no_cache=True, no_store=True)
@require_deploy_apps
def paginate_releases(request, domain, app_id):
    limit = request.GET.get('limit')
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    start_build_param = request.GET.get('start_build')
    if start_build_param and json.loads(start_build_param):
        start_build = json.loads(start_build_param)
        assert isinstance(start_build, int)
    else:
        start_build = {}
    timezone = get_timezone_for_user(request.couch_user, domain)
    saved_apps = get_db().view('app_manager/saved_app',
        startkey=[domain, app_id, start_build],
        endkey=[domain, app_id],
        descending=True,
        limit=limit,
        wrapper=lambda x: SavedAppBuild.wrap(x['value']).to_saved_build_json(timezone),
    ).all()
    include_media = toggles.APP_BUILDER_INCLUDE_MULTIMEDIA_ODK.enabled(
        request.user.username
    )
    for app in saved_apps:
        app['include_media'] = include_media and app['doc_type'] != 'RemoteApp'
    return json_response(saved_apps)


@require_deploy_apps
def release_manager(request, domain, app_id, template='app_manager/releases.html'):
    app = get_app(domain, app_id)
    context = get_apps_base_context(request, domain, app)
    can_send_sms = domain_has_privilege(domain, privileges.OUTBOUND_SMS)

    context.update({
        'release_manager': True,
        'can_send_sms': can_send_sms,
        'sms_contacts': (
            get_sms_autocomplete_context(request, domain)['sms_contacts']
            if can_send_sms else []
        ),
    })
    if not app.is_remote_app():
        # Multimedia is not supported for remote applications at this time.
        # todo remove get_media_references
        multimedia = app.get_media_references()
        context.update({
            'multimedia': multimedia,
        })
    response = render(request, template, context)
    response.set_cookie('lang', encode_if_unicode(context['lang']))
    return response


@login_and_domain_required
def current_app_version(request, domain, app_id):
    """
    Return current app version and the latest release
    """
    app = get_app(domain, app_id)
    latest = get_db().view('app_manager/saved_app',
        startkey=[domain, app_id, {}],
        endkey=[domain, app_id],
        descending=True,
        limit=1,
    ).first()
    latest_release = latest['value']['version'] if latest else None
    return json_response({
        'currentVersion': app.version,
        'latestRelease': latest_release,
    })


@no_conflict_require_POST
@require_can_edit_apps
def release_build(request, domain, app_id, saved_app_id):
    is_released = request.POST.get('is_released') == 'true'
    ajax = request.POST.get('ajax') == 'true'
    saved_app = get_app(domain, saved_app_id)
    if saved_app.copy_of != app_id:
        raise Http404
    saved_app.is_released = is_released
    saved_app.save(increment_version=False)
    from corehq.apps.app_manager.signals import app_post_release
    app_post_release.send(Application, application=saved_app)
    if ajax:
        return json_response({'is_released': is_released})
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
            copy = app.make_build(
                comment=comment,
                user_id=request.couch_user.get_id,
                previous_version=app.get_latest_app(released_only=False)
            )
            copy.save(increment_version=False)
        finally:
            # To make a RemoteApp always available for building
            if app.is_remote_app():
                app.save(increment_version=True)
    else:
        copy = None
    copy = copy and SavedAppBuild.wrap(copy.to_json()).to_saved_build_json(
        get_timezone_for_user(request.couch_user, domain)
    )
    lang, langs = get_langs(request, app)
    return json_response({
        "saved_app": copy,
        "error_html": render_to_string('app_manager/partials/build_errors.html', {
            'app': get_app(domain, app_id),
            'build_errors': errors,
            'domain': domain,
            'langs': langs,
            'lang': lang
        }),
    })


@no_conflict_require_POST
@require_can_edit_apps
def revert_to_copy(request, domain, app_id):
    """
    Copies a saved doc back to the original.
    See VersionedDoc.revert_to_copy

    """
    app = get_app(domain, app_id)
    copy = get_app(domain, request.POST['saved_app'])
    app = app.make_reversion_to_copy(copy)
    app.save()
    messages.success(
        request,
        "Successfully reverted to version %s, now at version %s" % (copy.version, app.version)
    )
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
    app = get_app(domain, app_id)
    qr_code_view = "odk_qr_code" if not with_media else "odk_media_qr_code"
    context = {
        "domain": domain,
        "app": app,
        "qr_code": reverse("corehq.apps.app_manager.views.%s" % qr_code_view, args=[domain, app_id]),
        "profile_url": app.odk_profile_display_url if not with_media else app.odk_media_profile_display_url,
    }
    return render(request, "app_manager/odk_install.html", context)


def odk_qr_code(request, domain, app_id):
    qr_code = get_app(domain, app_id).get_odk_qr_code()
    return HttpResponse(qr_code, content_type="image/png")


def odk_media_qr_code(request, domain, app_id):
    qr_code = get_app(domain, app_id).get_odk_qr_code(with_media=True)
    return HttpResponse(qr_code, content_type="image/png")


def short_url(request, domain, app_id):
    short_url = get_app(domain, app_id).get_short_url()
    return HttpResponse(short_url)


def short_odk_url(request, domain, app_id, with_media=False):
    short_url = get_app(domain, app_id).get_short_odk_url(with_media=with_media)
    return HttpResponse(short_url)


@require_deploy_apps
def update_build_comment(request, domain, app_id):
    build_id = request.POST.get('build_id')
    try:
        build = SavedAppBuild.get(build_id)
    except ResourceNotFound:
        raise Http404()
    build.build_comment = request.POST.get('comment')
    build.save()
    return json_response({'status': 'success'})
