from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dimagi.utils.couch.database import iter_docs

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans


def get_public_webform_form_paths(domain, webforms):
    """Iterate through all apps and builds referenced by included
    PublicWebforms to get URLs and display names.

    For performance, ``webforms`` should be limited to a reasonable number,
    e.g., 100, which is typically the max passed by a paginated table view.
    """
    webforms = list(webforms)
    builds = _get_apps(domain, {webform.app_build_id for webform in webforms})
    apps = _get_apps(domain, {webform.app_id for webform in webforms})
    return {
        webform.id: _form_path(webform, apps, builds, domain)
        for webform in webforms
    }


def _form_path(webform, apps, builds, domain):
    menu_name, form_name = _menu_and_form_names(webform, builds)
    return {
        'app_name': _app_name(webform, apps, builds),
        'app_url': _app_url(webform, apps, domain),
        'app_version': _app_version(webform, builds),
        'menu_name': menu_name,
        'form_name': form_name,
    }


def _get_apps(domain, app_ids):
    apps = {}
    for doc in iter_docs(Application.get_db(), list(app_ids)):
        if doc.get('domain') != domain or doc['doc_type'].endswith('-Deleted'):
            continue
        apps[doc['_id']] = doc
    return apps


def _app_name(webform, apps, builds):
    named_app = apps.get(webform.app_id)
    if named_app:
        return named_app['name']
    else:
        named_build = builds.get(webform.app_build_id)
        return "{} {}".format(named_build['name'], _("(Deleted)")) if named_build else None


def _app_url(webform, apps, domain):
    live_app = apps.get(webform.app_id)
    return reverse('view_app', args=[domain, webform.app_id]) if live_app else None


def _app_version(webform, builds):
    build = builds.get(webform.app_build_id)
    return build['version'] if build else None


def _menu_and_form_names(webform, builds):
    build = builds.get(webform.app_build_id)
    if not build:
        return None, None
    langs = [build.get('default_language')] + build.get('langs', [])
    for module in build.get('modules', []):
        for form in module.get('forms', []):
            if form.get('unique_id') == webform.form_unique_id:
                return (
                    clean_trans(module['name'], langs),
                    clean_trans(form['name'], langs),
                )
    return None, None
