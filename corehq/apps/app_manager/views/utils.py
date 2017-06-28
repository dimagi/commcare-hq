import json
import uuid
from urllib import urlencode
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app, wrap_app
from corehq.apps.app_manager.decorators import require_deploy_apps
from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import Application, ReportModule

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


def overwrite_app(app, master_build, include_ucrs=False, report_map=None):
    excluded_fields = set(Application._meta_fields).union(
        ['date_created', 'build_profiles', 'copy_history', 'copy_of', 'name', 'comment', 'doc_type']
    )
    master_json = master_build.to_json()
    for key, value in master_json.iteritems():
        if key not in excluded_fields:
            app[key] = value
    app['version'] = master_json['version']
    wrapped_app = wrap_app(app)
    for module in wrapped_app.modules:
        if isinstance(module, ReportModule):
            if include_ucrs and report_map is not None:
                for config in module.report_configs:
                    config.report_id = report_map[config.report_id]
            else:
                raise AppEditingError()
    wrapped_app.copy_attachments(master_build)
    wrapped_app.save(increment_version=False)
