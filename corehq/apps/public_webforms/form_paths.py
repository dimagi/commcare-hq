"""Name the app, menu, and form behind each public webform on the dashboard.

Names come from the build the webform is pinned to, so they describe what
respondents actually get, and survive a rename or a deletion. The canonical
app decides only what can be linked into the app builder.
"""
from collections import namedtuple

from couchdbkit.exceptions import DocTypeError

from django.urls import reverse

from dimagi.utils.couch.database import iter_docs

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
)
from corehq.apps.app_manager.models import Application

FormPathSegment = namedtuple('FormPathSegment', 'name url is_deleted')


def get_public_webform_form_paths(domain, webforms):
    """Return ``{webform.id: [FormPathSegment, ...]}``, the app, menu, and form
    a webform points at.

    Both reads are in bulk, so a page of webforms costs two requests rather
    than two per row.
    """
    webforms = list(webforms)
    builds = _get_apps(domain, {webform.app_build_id for webform in webforms})
    apps = _get_apps(domain, {webform.app_id for webform in webforms})
    return {
        webform.id: _form_path(domain, webform, builds, apps)
        for webform in webforms
    }


def _get_apps(domain, app_ids):
    """Wrapped apps by id, skipping any that are missing or deleted."""
    apps = {}
    for doc in iter_docs(Application.get_db(), list(app_ids)):
        # deleting an app only suffixes its doc type, and it still wraps, so
        # the doc type is the only thing that says the app is gone
        if doc.get('domain') != domain or doc['doc_type'].endswith('-Deleted'):
            continue
        try:
            apps[doc['_id']] = wrap_app(doc)
        except DocTypeError:
            pass
    return apps


def _form_path(domain, webform, builds, apps):
    build = builds.get(webform.app_build_id)
    app = apps.get(webform.app_id)
    named = build or app
    form = _get_form(named, webform.form_unique_id)
    menu = form.get_module() if form else None
    menu_id = menu.get_or_create_unique_id() if menu else None
    return _mark_deleted([
        _segment(
            named.name if named else '',
            exists=app is not None,
            urlname='view_app',
            url_args=[domain, webform.app_id],
        ),
        _segment(
            menu.default_name() if menu else '',
            exists=_get_menu(app, menu_id) is not None,
            urlname='view_module',
            url_args=[domain, webform.app_id, menu_id],
        ),
        _segment(
            form.default_name() if form else '',
            exists=_get_form(app, webform.form_unique_id) is not None,
            urlname='view_form',
            url_args=[domain, webform.app_id, webform.form_unique_id],
        ),
    ])


def _segment(name, exists, urlname, url_args):
    return FormPathSegment(
        name=name,
        url=reverse(urlname, args=url_args) if exists else None,
        is_deleted=False,
    )


def _mark_deleted(segments):
    """Mark only the outermost missing segment: a deleted app takes its menus
    and forms with it, and saying so three times reads as three problems."""
    for index, segment in enumerate(segments):
        if segment.name and not segment.url:
            segments[index] = segment._replace(is_deleted=True)
            break
    return segments


def _get_form(app, form_unique_id):
    if app is None:
        return None
    try:
        return app.get_form(form_unique_id)
    except FormNotFoundException:
        return None


def _get_menu(app, menu_id):
    if app is None or menu_id is None:
        return None
    try:
        return app.get_module_by_unique_id(menu_id)
    except ModuleNotFoundException:
        return None
