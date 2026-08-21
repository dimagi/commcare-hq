from couchdbkit.exceptions import DocTypeError

from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from dimagi.utils.couch.database import iter_docs

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.models import Application


def get_public_webform_form_paths(domain, webforms):
    webforms = list(webforms)
    builds = _get_apps(domain, {webform.app_build_id for webform in webforms})
    apps = _get_apps(domain, {webform.app_id for webform in webforms})
    return {
        webform.id: {
            'app_name': _app_name(webform, apps, builds),
            'app_url': _app_url(webform, apps, domain),
            'app_version': _app_version(webform, builds),
            'menu_name': _menu_name(webform, builds),
            'form_name': _form_name(webform, builds),
        } for webform in webforms
    }


def _get_apps(domain, app_ids):
    apps = {}
    for doc in iter_docs(Application.get_db(), list(app_ids)):
        if doc.get('domain') != domain or doc['doc_type'].endswith('-Deleted'):
            continue
        try:
            apps[doc['_id']] = wrap_app(doc)
        except DocTypeError:
            pass
    return apps


def _app_name(webform, apps, builds):
    named_app = apps.get(webform.app_id)
    if named_app:
        return named_app.name
    else:
        named_build = builds.get(webform.app_build_id)
        return "{} {}".format(named_build.name, _("(Deleted)")) if named_build else None


def _app_url(webform, apps, domain):
    live_app = apps.get(webform.app_id)
    return reverse('view_app', args=[domain, webform.app_id]) if live_app else None


def _app_version(webform, builds):
    build = builds.get(webform.app_build_id)
    return build.version if build else None


def _menu_name(webform, builds):
    build = builds.get(webform.app_build_id)
    form = build.get_form(webform.form_unique_id) if build else None
    menu = form.get_module() if form else None
    return menu.default_name() if menu else None


def _form_name(webform, builds):
    build = builds.get(webform.app_build_id)
    form = build.get_form(webform.form_unique_id) if build else None
    return form.default_name() if form else None
