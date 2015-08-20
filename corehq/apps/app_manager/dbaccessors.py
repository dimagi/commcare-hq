from corehq.apps.app_manager.util import get_correct_app_class
from couchdbkit.exceptions import DocTypeError
from couchdbkit.resource import ResourceNotFound
from dimagi.utils.couch.database import get_db
from django.http import Http404


def domain_has_apps(domain):
    from .models import Application
    results = Application.get_db().view('app_manager/applications_brief',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        limit=1,
    ).all()
    return len(results) > 0


def get_app(domain, app_id, wrap_cls=None, latest=False, target=None):
    """
    Utility for getting an app, making sure it's in the domain specified, and wrapping it in the right class
    (Application or RemoteApp).

    """

    if latest:
        try:
            original_app = get_db().get(app_id)
        except ResourceNotFound:
            raise Http404()
        if not domain:
            try:
                domain = original_app['domain']
            except Exception:
                raise Http404()

        if original_app.get('copy_of'):
            parent_app_id = original_app.get('copy_of')
            min_version = original_app['version'] if original_app.get('is_released') else -1
        else:
            parent_app_id = original_app['_id']
            min_version = -1

        if target == 'build':
            # get latest-build regardless of star
            couch_view = 'app_manager/saved_app'
            startkey = [domain, parent_app_id, {}]
            endkey = [domain, parent_app_id]
        else:
            # get latest starred-build
            couch_view = 'app_manager/applications'
            startkey = ['^ReleasedApplications', domain, parent_app_id, {}]
            endkey = ['^ReleasedApplications', domain, parent_app_id, min_version]

        latest_app = get_db().view(
            couch_view,
            startkey=startkey,
            endkey=endkey,
            limit=1,
            descending=True,
            include_docs=True
        ).one()

        try:
            app = latest_app['doc']
        except TypeError:
            # If no builds/starred-builds, return act as if latest=False
            app = original_app
    else:
        try:
            app = get_db().get(app_id)
        except Exception:
            raise Http404()
    if domain and app['domain'] != domain:
        raise Http404()
    try:
        cls = wrap_cls or get_correct_app_class(app)
    except DocTypeError:
        raise Http404()
    app = cls.wrap(app)
    return app


def get_apps_in_domain(domain, full=False, include_remote=True):
    """
    Returns all apps(not builds) in a domain

    full use applications when true, otherwise applications_brief
    """
    if full:
        view_name = 'app_manager/applications'
        startkey = [domain, None]
        endkey = [domain, None, {}]
    else:
        view_name = 'app_manager/applications_brief'
        startkey = [domain]
        endkey = [domain, {}]

    from .models import Application
    view_results = Application.get_db().view(view_name,
        startkey=startkey,
        endkey=endkey,
        include_docs=True)

    remote_app_filter = None if include_remote else lambda app: not app.is_remote_app()
    wrapped_apps = [get_correct_app_class(row['doc']).wrap(row['doc']) for row in view_results]
    return filter(remote_app_filter, wrapped_apps)
