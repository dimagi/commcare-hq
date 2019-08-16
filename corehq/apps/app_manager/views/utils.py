from __future__ import absolute_import
from __future__ import unicode_literals
import json
import uuid
from functools import partial
from six.moves.urllib.parse import urlencode
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    wrap_app,
    get_apps_in_domain,
    get_current_app,
)
from corehq.apps.app_manager.decorators import require_deploy_apps
from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    ModuleNotFoundException,
    FormNotFoundException,
    AppLinkError,
    MultimediaMissingError,
)
from corehq.apps.app_manager.models import (
    Application,
    enable_usercase_if_necessary,
    CustomIcon,
)
from corehq.apps.es import FormES
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.linked_domain.exceptions import (
    RemoteRequestError,
    RemoteAuthError,
    ActionNotPermitted,
)
from corehq.apps.linked_domain.models import AppLinkDetail
from corehq.apps.linked_domain.util import pull_missing_multimedia_for_app

from corehq.apps.app_manager.util import update_form_unique_ids
from corehq.apps.userreports.util import get_static_report_mapping
import six

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
    return s.encode('utf-8') if isinstance(s, six.text_type) else s


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
        'xmlns': str(uuid.uuid4()).upper(),
        'name': form_name,
    })


def get_default_followup_form_xml(context):
    """Update context and apply in XML file default_followup_form"""
    context.update({'xmlns_uuid': str(uuid.uuid4()).upper()})
    return render_to_string("app_manager/default_followup_form.xml", context=context)


def overwrite_app(app, master_build, report_map=None):
    excluded_fields = set(Application._meta_fields).union([
        'date_created', 'build_profiles', 'copy_history', 'copy_of',
        'name', 'comment', 'doc_type', '_LAZY_ATTACHMENTS', 'practice_mobile_worker_id',
        'custom_base_url', 'progenitor_app_id'
    ])
    master_json = master_build.to_json()
    app_json = app.to_json()
    form_ids_by_xmlns = _get_form_ids_by_xmlns(app_json)  # do this before we change the source

    for key, value in six.iteritems(master_json):
        if key not in excluded_fields:
            app_json[key] = value
    app_json['version'] = master_json['version']
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

    wrapped_app = _update_form_ids(wrapped_app, master_build, form_ids_by_xmlns)
    enable_usercase_if_necessary(wrapped_app)
    return wrapped_app


def _get_form_ids_by_xmlns(app):
    id_map = {}
    for module in app['modules']:
        for form in module['forms']:
            id_map[form['xmlns']] = form['unique_id']
    return id_map


def _update_form_ids(app, master_app, form_ids_by_xmlns):

    _attachments = master_app.get_attachments()

    app_source = app.to_json()
    app_source.pop('external_blobs')
    app_source['_attachments'] = _attachments

    updated_source = update_form_unique_ids(app_source, form_ids_by_xmlns)

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
        return any(is_set(profile) for _, profile in app.build_profiles.items())

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
        for _, profile in six.iteritems(app.build_profiles):
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


def update_linked_app_and_notify(domain, app_id, user_id, email):
    app = get_current_app(domain, app_id)
    subject = _("Update Status for linked app %s") % app.name
    try:
        update_linked_app(app, user_id)
    except (AppLinkError, MultimediaMissingError) as e:
        message = six.text_type(e)
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


def update_linked_app(app, user_id, master_build=None):
    if not app.domain_link:
        raise AppLinkError(_(
            'This project is not authorized to update from the master application. '
            'Please contact the maintainer of the master app if you believe this is a mistake. '
        ))

    if master_build:
        master_version = master_build.version
    else:
        try:
            master_version = app.get_master_version()
        except RemoteRequestError:
            raise AppLinkError(_(
                'Unable to pull latest master from remote CommCare HQ. Please try again later.'
            ))

    if app.version is None or master_version > app.version:
        if not master_build:
            try:
                master_build = app.get_latest_master_release()
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


def clear_xmlns_app_id_cache(domain):
    from couchforms.analytics import get_all_xmlns_app_id_pairs_submitted_to_in_domain
    get_all_xmlns_app_id_pairs_submitted_to_in_domain.clear(domain)


def form_has_submissions(domain, app_id, xmlns):
    return FormES().domain(domain).app([app_id]).xmlns([xmlns]).count() != 0
