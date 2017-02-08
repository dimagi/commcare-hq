from future import standard_library
standard_library.install_aliases()
from builtins import str
import json
from urllib.parse import urlencode
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_deploy_apps


CASE_TYPE_CONFLICT_MSG = (
    "Warning: The form's new module "
    "has a different case type from the old module.<br />"
    "Make sure all case properties you are loading "
    "are available in the new case type"
)


@require_deploy_apps
def back_to_main(request, domain, app_id=None, module_id=None, form_id=None,
                 unique_form_id=None):
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

    if app_id is not None:
        args.append(app_id)
        if unique_form_id is not None:
            app = get_app(domain, app_id)
            obj = app.get_form(unique_form_id, bare=False)
            module_id = obj['module'].id
            form_id = obj['form'].id
        if module_id is not None:
            args.append(module_id)
            if form_id is not None:
                args.append(form_id)

    if page:
        view_name = page
    else:
        view_name = {
            1: 'default_app',
            2: 'view_app',
            3: 'view_module',
            4: 'form_source' if toggles.APP_MANAGER_V2.enabled(domain) else 'view_form',
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
    return s.encode('utf-8') if isinstance(s, str) else s


def validate_langs(request, existing_langs):
    o = json.loads(request.body)
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
