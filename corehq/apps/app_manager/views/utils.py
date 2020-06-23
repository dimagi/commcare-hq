import json
from collections import defaultdict
from functools import partial

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_app_cached,
    get_apps_in_domain,
    get_current_app,
    wrap_app,
)
from corehq.apps.app_manager.decorators import require_deploy_apps
from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    AppLinkError,
    FormNotFoundException,
    ModuleNotFoundException,
    MultimediaMissingError,
)
from corehq.apps.app_manager.models import (
    Application,
    CustomIcon,
    enable_usercase_if_necessary,
)
from corehq.apps.app_manager.util import generate_xmlns, update_form_unique_ids
from corehq.apps.es import FormES
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.linked_domain.exceptions import (
    ActionNotPermitted,
    RemoteAuthError,
    RemoteRequestError,
)
from corehq.apps.linked_domain.models import AppLinkDetail
from corehq.apps.linked_domain.util import pull_missing_multimedia_for_app
from corehq.apps.userreports.util import get_static_report_mapping

CASE_TYPE_CONFLICT_MSG = (
    "Warning: The form's new module "
    "has a different case type from the old module.<br />"
    "Make sure all case properties you are loading "
    "are available in the new case type"
)


@require_deploy_apps
def back_to_main(request, domain, app_id, module_id=None, form_id=None,
                 form_unique_id=None, module_unique_id=None):
    """
    returns an HttpResponseRedirect back to the main page for the App Manager app
    with the correct GET parameters.

    This is meant to be used by views that process a POST request,
    which then redirect to the main page.

    """
    args = [domain, app_id]
    view_name = 'view_app'

    app = get_app(domain, app_id)

    module = None
    try:
        if module_id is not None:
            module = app.get_module(module_id)
        elif module_unique_id is not None:
            module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        raise Http404()

    form = None
    if form_id is not None and module is not None:
        try:
            form = module.get_form(form_id)
        except IndexError:
            raise Http404()
    elif form_unique_id is not None:
        try:
            form = app.get_form(form_unique_id)
        except FormNotFoundException:
            raise Http404()

    if form is not None:
        view_name = 'view_form' if form.no_vellum else 'form_source'
        args.append(form.unique_id)
    elif module is not None:
        view_name = 'view_module'
        args.append(module.unique_id)

    return HttpResponseRedirect(reverse(view_name, args=args))


def get_langs(request, app):
    lang = request.GET.get(
        'lang',
        request.COOKIES.get('lang', app.langs[0] if hasattr(app, 'langs') and app.langs else '')
    )
    langs = None
    if app and hasattr(app, 'langs'):
        if not app.langs and not app.is_remote_app:
            # lots of things fail if the app doesn't have any languages.
            # the best we can do is add 'en' if there's nothing else.
            app.langs.append('en')
            app.save()
        if not lang or lang not in app.langs:
            lang = (app.langs or ['en'])[0]
        langs = [lang] + app.langs
    return lang, langs


def set_lang_cookie(response, lang):
    response.set_cookie('lang', encode_if_unicode(lang))


def bail(request, domain, app_id, not_found=""):
    if not_found:
        messages.error(request, 'Oops! We could not find that %s. Please try again' % not_found)
    else:
        messages.error(request, 'Oops! We could not complete your request. Please try again')
    return back_to_main(request, domain, app_id)


def encode_if_unicode(s):
    return s.encode('utf-8') if isinstance(s, str) else s


def validate_langs(request, existing_langs):
    o = json.loads(request.body.decode('utf-8'))
    langs = o['langs']
    rename = o['rename']

    assert set(rename.keys()).issubset(existing_langs)
    assert set(rename.values()).issubset(langs)
    # assert that there are no repeats in the values of rename
    assert len(set(rename.values())) == len(list(rename.values()))
    # assert that no lang is renamed to an already existing lang
    for old, new in rename.items():
        if old != new:
            assert(new not in existing_langs)

    return (langs, rename)


def get_blank_form_xml(form_name):
    return render_to_string("app_manager/blank_form.xml", context={
        'xmlns': generate_xmlns(),
        'name': form_name,
    })


def get_default_followup_form_xml(context):
    """Update context and apply in XML file default_followup_form"""
    context.update({'xmlns_uuid': generate_xmlns()})
    return render_to_string("app_manager/default_followup_form.xml", context=context)


def overwrite_app(app, master_build, report_map=None):
    excluded_fields = set(Application._meta_fields).union([
        'date_created', 'build_profiles', 'copy_history', 'copy_of',
        'name', 'comment', 'doc_type', '_LAZY_ATTACHMENTS', 'practice_mobile_worker_id',
        'custom_base_url', 'family_id',
    ])
    master_json = master_build.to_json()
    app_json = app.to_json()

    for key, value in master_json.items():
        if key not in excluded_fields:
            app_json[key] = value
    app_json['version'] = app_json.get('version', 1)
    app_json['upstream_version'] = master_json['version']
    app_json['upstream_app_id'] = master_json['copy_of']
    wrapped_app = wrap_app(app_json)
    for module in wrapped_app.get_report_modules():
        if report_map is None:
            raise AppEditingError('Report map not passed to overwrite_app')

        for config in module.report_configs:
            try:
                config.report_id = report_map[config.report_id]
            except KeyError:
                raise AppEditingError(config.report_id)

    # Legacy linked apps have different form unique ids than their master app(s). These mappings
    # are stored as ResourceOverride objects. Look up to see if this app has any.
    from corehq.apps.app_manager.suite_xml.post_process.resources import get_xform_resource_overrides
    overrides = get_xform_resource_overrides(domain=wrapped_app.domain, app_id=wrapped_app.get_id)
    ids_map = {pre_id: override.post_id for pre_id, override in overrides.items()}
    wrapped_app = _update_forms(wrapped_app, master_build, ids_map)

    # Multimedia versions should be set based on the linked app's versions, not those of the master app.
    for path in wrapped_app.multimedia_map.keys():
        wrapped_app.multimedia_map[path].version = None
    wrapped_app.set_media_versions()

    enable_usercase_if_necessary(wrapped_app)
    return wrapped_app


def _update_forms(app, master_app, ids_map):

    _attachments = master_app.get_attachments()

    app_source = app.to_json()
    app_source.pop('external_blobs')
    app_source['_attachments'] = _attachments

    updated_source = update_form_unique_ids(app_source, ids_map, update_all=False)

    attachments = app_source.pop('_attachments')
    new_wrapped_app = wrap_app(updated_source)
    save = partial(new_wrapped_app.save, increment_version=False)
    return new_wrapped_app.save_attachments(attachments, save)


def get_practice_mode_configured_apps(domain, mobile_worker_id=None):

    def is_set(app_or_profile):
        if mobile_worker_id:
            if app_or_profile.practice_mobile_worker_id == mobile_worker_id:
                return True
        else:
            if app_or_profile.practice_mobile_worker_id:
                return True

    def _practice_mode_configured(app):
        if is_set(app):
            return True
        return any(is_set(profile) for profile in app.build_profiles.values())

    return [app for app in get_apps_in_domain(domain) if _practice_mode_configured(app)]


def unset_practice_mode_configured_apps(domain, mobile_worker_id=None):
    """
    Unset practice user for apps that have a practice user configured directly or
    on a build profile of apps in the domain. If a mobile_worker_id is specified,
    only apps configured with that user will be unset

    returns:
        list of apps on which the practice user was unset

    kwargs:
        mobile_worker_id: id of mobile worker. If this is specified, only those apps
        configured with this mobile worker will be unset. If not, apps that are configured
        with any mobile worker are unset
    """

    def unset_user(app_or_profile):
        if mobile_worker_id:
            if app_or_profile.practice_mobile_worker_id == mobile_worker_id:
                app_or_profile.practice_mobile_worker_id = None
        else:
            if app_or_profile.practice_mobile_worker_id:
                app_or_profile.practice_mobile_worker_id = None

    apps = get_practice_mode_configured_apps(domain, mobile_worker_id)
    for app in apps:
        unset_user(app)
        for profile in app.build_profiles.values():
            unset_user(profile)
        app.save()

    return apps


def handle_custom_icon_edits(request, form_or_module, lang):
    if toggles.CUSTOM_ICON_BADGES.enabled(request.domain):
        icon_text_body = request.POST.get("custom_icon_text_body")
        icon_xpath = request.POST.get("custom_icon_xpath")
        icon_form = request.POST.get("custom_icon_form")

        # if there is a request to set custom icon
        if icon_form:
            # validate that only of either text or xpath should be present
            if (icon_text_body and icon_xpath) or (not icon_text_body and not icon_xpath):
                return _("Please enter either text body or xpath for custom icon")

            # a form should have just one custom icon for now
            # so this just adds a new one with params or replaces the existing one with new params
            form_custom_icon = (form_or_module.custom_icon if form_or_module.custom_icon else CustomIcon())
            form_custom_icon.form = icon_form
            form_custom_icon.text[lang] = icon_text_body
            form_custom_icon.xpath = icon_xpath

            form_or_module.custom_icons = [form_custom_icon]

        # if there is a request to unset custom icon
        if not icon_form and form_or_module.custom_icon:
            form_or_module.custom_icons = []


def update_linked_app_and_notify(domain, app_id, master_app_id, user_id, email):
    app = get_current_app(domain, app_id)
    subject = _("Update Status for linked app %s") % app.name
    try:
        update_linked_app(app, master_app_id, user_id)
    except (AppLinkError, MultimediaMissingError) as e:
        message = str(e)
    except Exception:
        # Send an email but then crash the process
        # so we know what the error was
        send_html_email_async.delay(subject, email, _(
            "Something went wrong updating your linked app. "
            "Our team has been notified and will monitor the situation. "
            "Please try again, and if the problem persists report it as an issue."))
        raise
    else:
        message = _("Your linked application was successfully updated to the latest version.")
    send_html_email_async.delay(subject, email, message)


def update_linked_app(app, master_app_id_or_build, user_id):
    if not app.domain_link:
        raise AppLinkError(_(
            'This project is not authorized to update from the master application. '
            'Please contact the maintainer of the master app if you believe this is a mistake. '
        ))

    if isinstance(master_app_id_or_build, str):
        try:
            master_build = app.get_latest_master_release(master_app_id_or_build)
        except ActionNotPermitted:
            raise AppLinkError(_(
                'This project is not authorized to update from the master application. '
                'Please contact the maintainer of the master app if you believe this is a mistake. '
            ))
        except RemoteAuthError:
            raise AppLinkError(_(
                'Authentication failure attempting to pull latest master from remote CommCare HQ.'
                'Please verify your authentication details for the remote link are correct.'
            ))
        except RemoteRequestError:
            raise AppLinkError(_(
                'Unable to pull latest master from remote CommCare HQ. Please try again later.'
            ))
    else:
        master_build = master_app_id_or_build
    master_app_id = master_build.master_id

    previous = app.get_latest_build_from_upstream(master_app_id)
    if (
        previous is None
        or master_build.version > previous.upstream_version
        or toggles.MULTI_MASTER_LINKED_DOMAINS.enabled(app.domain)
    ):
        old_multimedia_ids = set([media_info.multimedia_id for path, media_info in app.multimedia_map.items()])
        report_map = get_static_report_mapping(master_build.domain, app['domain'])

        try:
            app = overwrite_app(app, master_build, report_map)
        except AppEditingError as e:
            raise AppLinkError(
                _(
                    'This application uses mobile UCRs '
                    'which are not available in the linked domain: {ucr_id}'
                ).format(ucr_id=str(e))
            )

        if app.master_is_remote:
            try:
                pull_missing_multimedia_for_app(app, old_multimedia_ids)
            except RemoteRequestError:
                raise AppLinkError(_(
                    'Error fetching multimedia from remote server. Please try again later.'
                ))

        # reapply linked application specific data
        app.reapply_overrides()
        app.save()

    app.domain_link.update_last_pull('app', user_id, model_details=AppLinkDetail(app_id=app._id))
    return app


def clear_xmlns_app_id_cache(domain):
    from couchforms.analytics import get_all_xmlns_app_id_pairs_submitted_to_in_domain
    get_all_xmlns_app_id_pairs_submitted_to_in_domain.clear(domain)


def form_has_submissions(domain, app_id, xmlns):
    return FormES().domain(domain).app([app_id]).xmlns([xmlns]).count() != 0


def get_new_multimedia_between_builds(domain, target_build_id, source_build_id, build_profile_id=None):
    def _get_mm_map_by_id(multimedia_map):
        return {
            media_map_item['multimedia_id']: media_map_item
            for path, media_map_item in
            multimedia_map.items()
        }

    source_build = get_app_cached(domain, source_build_id)
    target_build = get_app_cached(domain, target_build_id)
    assert source_build.copy_of, _("Size calculation available only for builds")
    assert target_build.copy_of, _("Size calculation available only for builds")
    build_profile = source_build.build_profiles.get(build_profile_id) if build_profile_id else None
    source_mm_map = source_build.multimedia_map_for_build(build_profile=build_profile)
    target_mm_map = target_build.multimedia_map_for_build(build_profile=build_profile)
    source_mm_map_by_id = _get_mm_map_by_id(source_mm_map)
    target_mm_map_by_id = _get_mm_map_by_id(target_mm_map)
    added = set(target_mm_map_by_id.keys()).difference(set(source_mm_map_by_id.keys()))
    media_objects = {
        mm.get_id: mm
        for path, mm in
        target_build.get_media_objects(multimedia_map=target_mm_map)
    }
    total_size = defaultdict(lambda: 0)
    for multimedia_id in added:
        media_object = media_objects[multimedia_id]
        total_size[media_object.doc_type] += media_object.content_length
    return total_size


def get_multimedia_sizes_for_build(domain, build_id, build_profile_id=None):
    build = get_app_cached(domain, build_id)
    assert build.copy_of, _("Size calculation available only for builds")
    build_profile = build.build_profiles.get(build_profile_id) if build_profile_id else None
    multimedia_map_for_build = build.multimedia_map_for_build(build_profile=build_profile)
    multimedia_map_for_build_by_id = {
        media_map_item['multimedia_id']: media_map_item
        for path, media_map_item in
        multimedia_map_for_build.items()
    }
    media_objects = {
        mm_object.get_id: mm_object
        for path, mm_object in
        build.get_media_objects(multimedia_map=multimedia_map_for_build)
    }
    total_size = defaultdict(lambda: 0)
    for multimedia_id, media_item in multimedia_map_for_build_by_id.items():
        media_object = media_objects[multimedia_id]
        total_size[media_object.doc_type] += media_object.content_length
    return total_size
