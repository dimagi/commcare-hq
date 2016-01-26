from couchdbkit.exceptions import DocTypeError
from couchdbkit.resource import ResourceNotFound
from django.http import Http404

from corehq.apps.es import AppES


def domain_has_apps(domain):
    from .models import Application
    results = Application.get_db().view('app_manager/applications_brief',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        limit=1,
    ).all()
    return len(results) > 0


def get_latest_released_app_doc(domain, app_id, min_version=None):
    """Get the latest starred build for the application"""
    from .models import Application
    key = ['^ReleasedApplications', domain, app_id]
    app = Application.get_db().view(
        'app_manager/applications',
        startkey=key + [{}],
        endkey=(key + [min_version]) if min_version is not None else key,
        descending=True,
        include_docs=True
    ).first()
    return app['doc'] if app else None


def _get_latest_build_view(domain, app_id, include_docs):
    from .models import Application
    return Application.get_db().view(
        'app_manager/saved_app',
        startkey=[domain, app_id, {}],
        endkey=[domain, app_id],
        descending=True,
        include_docs=include_docs,
    ).first()


def get_latest_build_doc(domain, app_id):
    """Get the latest saved build of the application, regardless of star."""
    res = _get_latest_build_view(domain, app_id, include_docs=True)
    return res['doc'] if res else None


def get_latest_build_id(domain, app_id):
    """Get id of the latest build of the application, regardless of star."""
    res = _get_latest_build_view(domain, app_id, include_docs=False)
    return res['id'] if res else None


def get_app(domain, app_id, wrap_cls=None, latest=False, target=None):
    """
    Utility for getting an app, making sure it's in the domain specified, and wrapping it in the right class
    (Application or RemoteApp).

    """
    from .models import Application
    from corehq.apps.app_manager.util import get_correct_app_class

    if latest:
        try:
            original_app = Application.get_db().get(app_id)
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
            app = get_latest_build_doc(domain, parent_app_id)
        else:
            app = get_latest_released_app_doc(domain, parent_app_id, min_version=min_version)

        if not app:
            # If no builds/starred-builds, act as if latest=False
            app = original_app
    else:
        try:
            app = Application.get_db().get(app_id)
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


def get_apps_in_domain(domain, include_remote=True):
    from .models import Application
    from corehq.apps.app_manager.util import get_correct_app_class
    docs = [row['doc'] for row in Application.get_db().view(
        'app_manager/applications',
        startkey=[domain, None],
        endkey=[domain, None, {}],
        include_docs=True
    )]
    apps = [get_correct_app_class(doc).wrap(doc) for doc in docs]
    if not include_remote:
        apps = [app for app in apps if not app.is_remote_app()]
    return apps


def get_brief_apps_in_domain(domain, include_remote=True):
    from .models import Application
    from corehq.apps.app_manager.util import get_correct_app_class
    docs = [row['value'] for row in Application.get_db().view(
        'app_manager/applications_brief',
        startkey=[domain],
        endkey=[domain, {}]
    )]
    apps = [get_correct_app_class(doc).wrap(doc) for doc in docs]
    if not include_remote:
        apps = [app for app in apps if not app.is_remote_app()]
    return apps


def get_app_ids_in_domain(domain):
    from .models import Application
    return [row['id'] for row in Application.get_db().view(
        'app_manager/applications',
        startkey=[domain, None],
        endkey=[domain, None, {}]
    )]


def get_built_app_ids(domain):
    """
    Returns the app ids of all apps in the domain that have at least one build.
    """
    from .models import Application
    result = Application.get_db().view(
        'app_manager/saved_app',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
    )
    app_ids = [data.get('value', {}).get('copy_of') for data in result]
    app_ids = list(set(app_ids))
    return [app_id for app_id in app_ids if app_id]


def get_built_app_ids_for_app_id(domain, app_id, version=None):
    """
    Returns all the built apps for an application id. If version is specified returns all apps after that
    version.
    """
    from .models import Application
    key = [domain, app_id]
    skip = 1 if version else 0
    results = Application.get_db().view(
        'app_manager/saved_app',
        startkey=key + [version],
        endkey=key + [{}],
        reduce=False,
        include_docs=False,
        skip=skip
    ).all()
    return [result['id'] for result in results]


def get_all_apps(domain):
    """
    Returns a list of all the apps ever built and current Applications.
    Used for subscription management when apps use subscription only features
    that shouldn't be present in built apps as well as app definitions.
    """
    from .models import Application
    from corehq.apps.app_manager.util import get_correct_app_class
    saved_apps = Application.get_db().view(
        'app_manager/saved_app',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
    )
    all_apps = [get_correct_app_class(row['doc']).wrap(row['doc']) for row in saved_apps]
    all_apps.extend(get_apps_in_domain(domain))
    return all_apps


def get_case_types_from_apps(domain):
    """Get the case types of modules in applications in the domain."""
    q = (AppES()
         .domain(domain)
         .size(0)
         .terms_facet('modules.case_type.exact', 'case_types'))
    return q.run().facets.case_types.terms
