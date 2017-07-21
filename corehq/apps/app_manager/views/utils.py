import json
import re
import uuid
from urllib import urlencode
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app, wrap_app, get_apps_in_domain
from corehq.apps.app_manager.decorators import require_deploy_apps
from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import Application, ReportModule, ATTACHMENT_REGEX

from dimagi.utils.make_uuid import random_hex

CASE_TYPE_CONFLICT_MSG = (
    "Warning: The form's new module "
    "has a different case type from the old module.<br />"
    "Make sure all case properties you are loading "
    "are available in the new case type"
)


@require_deploy_apps
def back_to_main(request, domain, app_id=None, module_id=None, form_id=None,
                 form_unique_id=None):
    """
    returns an HttpResponseRedirect back to the main page for the App Manager app
    with the correct GET parameters.

    This is meant to be used by views that process a POST request,
    which then redirect to the main page.

    """
    # TODO: Refactor this function. The length of the args matters :(

    page = None
    params = {}

    args = [domain]
    form_view = 'form_source' if toggles.APP_MANAGER_V2.enabled(request.user.username) else 'view_form'

    if app_id is not None:
        args.append(app_id)
        if form_unique_id is not None:
            app = get_app(domain, app_id)
            obj = app.get_form(form_unique_id, bare=False)
            module_id = obj['module'].id
            form_id = obj['form'].id
            if obj['form'].no_vellum:
                form_view = 'view_form'
        if module_id is not None:
            args.append(module_id)
            if form_id is not None:
                args.append(form_id)
                app = get_app(domain, app_id)
                if app.get_module(module_id).get_form(form_id).no_vellum:
                    form_view = 'view_form'

    if page:
        view_name = page
    else:
        view_name = {
            1: 'default_app',
            2: 'view_app',
            3: 'view_module',
            4: form_view,
        }[len(args)]

    return HttpResponseRedirect(
        "%s%s" % (
            reverse(view_name, args=args),
            "?%s" % urlencode(params) if params else ""
        )
    )


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


def bail(request, domain, app_id, not_found=""):
    if not_found:
        messages.error(request, 'Oops! We could not find that %s. Please try again' % not_found)
    else:
        messages.error(request, 'Oops! We could not complete your request. Please try again')
    return back_to_main(request, domain, app_id)


def encode_if_unicode(s):
    return s.encode('utf-8') if isinstance(s, unicode) else s


def validate_langs(request, existing_langs):
    o = json.loads(request.body)
    langs = o['langs']
    rename = o['rename']

    assert set(rename.keys()).issubset(existing_langs)
    assert set(rename.values()).issubset(langs)
    # assert that there are no repeats in the values of rename
    assert len(set(rename.values())) == len(rename.values())
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


def overwrite_app(app, master_build, report_map=None, maintain_ids=False):
    excluded_fields = set(Application._meta_fields).union(
        ['date_created', 'build_profiles', 'copy_history', 'copy_of', 'name', 'comment', 'doc_type']
    )
    id_map = _get_form_id_map(app)
    master_json = master_build.to_json()
    for key, value in master_json.iteritems():
        if key not in excluded_fields:
            app[key] = value
    app['version'] = master_json['version']
    wrapped_app = wrap_app(app)
    for module in wrapped_app.modules:
        if isinstance(module, ReportModule):
            if report_map is not None:
                for config in module.report_configs:
                    try:
                        config.report_id = report_map[config.report_id]
                    except KeyError:
                        raise AppEditingError('Dynamic UCR used in linked app')
            else:
                raise AppEditingError('Report map not passed to overwrite_app')
    if maintain_ids:
        wrapped_app = _update_form_ids(wrapped_app, master_build, id_map)
    wrapped_app.save(increment_version=False)


def _get_form_id_map(app):
    id_map = {}
    for module in app['modules'].values():
        for form in module['forms'].values():
            id_map[form['xmlns']] = form['unique_id']
    return id_map


def _update_form_ids(app, master_app, id_map):
    from corehq.apps.app_manager.models import form_id_references, jsonpath_update

    id_changes = {}
    attachments = _get_attachments(master_app)

    for module in app.modules:
        for form in module.forms:
            new_id = id_map.get(form.xmlns, random_hex())
            id_changes[form.unique_id] = new_id
            if ("%s.xml" % form.unique_id) in attachments:
                attachments["%s.xml" % new_id] = attachments.pop("%s.xml" % form.unique_id)
            form.unique_id = new_id
    app_source = app.to_json()
    app_source.pop('external_blobs')

    for reference_path in form_id_references:
        for reference in reference_path.find(app_source):
            if reference.value in id_changes:
                jsonpath_update(reference, id_changes[reference.value])

    new_wrapped_app = Application.wrap(app_source)
    new_wrapped_app = _save_attachments(new_wrapped_app, attachments)
    return new_wrapped_app


def _get_attachments(app):
    attachments = {}
    for name in app.lazy_list_attachments():
        if re.match(ATTACHMENT_REGEX, name):
            # FIXME loss of metadata (content type, etc.)
            attachments[name] = app.lazy_fetch_attachment(name)
    return attachments


def _save_attachments(app, attachments):
    with app.atomic_blobs():
        for name, attachment in attachments.items():
            if re.match(ATTACHMENT_REGEX, name):
                app.put_attachment(attachment, name)
    return app


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
        for _, profile in app.build_profiles.iteritems():
            unset_user(profile)
        app.save()

    return apps
