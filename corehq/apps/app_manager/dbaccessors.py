from collections import namedtuple

from couchdbkit.exceptions import DocTypeError
from couchdbkit.resource import ResourceNotFound
from corehq.util.quickcache import quickcache
from django.http import Http404

from corehq.apps.es import AppES

AppBuildVersion = namedtuple('AppBuildVersion', ['app_id', 'build_id', 'version'])


@quickcache(['domain'], timeout=1 * 60 * 60)
def domain_has_apps(domain):
    from .models import Application
    results = Application.get_db().view('app_manager/applications_brief',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        limit=1,
    ).all()
    return len(results) > 0


def get_latest_released_app_doc(domain, app_id):
    """Get the latest starred build for the application"""
    from .models import Application
    key = ['^ReleasedApplications', domain, app_id]
    app = Application.get_db().view(
        'app_manager/applications',
        startkey=key + [{}],
        endkey=key,
        descending=True,
        include_docs=True,
        limit=1,
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
        limit=1,
    ).first()


def get_latest_build_doc(domain, app_id):
    """Get the latest saved build of the application, regardless of star."""
    res = _get_latest_build_view(domain, app_id, include_docs=True)
    return res['doc'] if res else None


def get_latest_build_id(domain, app_id):
    """Get id of the latest build of the application, regardless of star."""
    res = _get_latest_build_view(domain, app_id, include_docs=False)
    return res['id'] if res else None


def get_build_doc_by_version(domain, app_id, version):
    from .models import Application
    res = Application.get_db().view(
        'app_manager/saved_app',
        key=[domain, app_id, version],
        include_docs=True,
        reduce=False,
        limit=1,
    ).first()
    return res['doc'] if res else None


def wrap_app(app_doc, wrap_cls=None):
    """Will raise DocTypeError if it can't figure out the correct class"""
    from corehq.apps.app_manager.util import get_correct_app_class
    cls = wrap_cls or get_correct_app_class(app_doc)
    return cls.wrap(app_doc)


def get_current_app(domain, app_id):
    from .models import Application
    app = Application.get_db().get(app_id)
    if app.get('domain', None) != domain:
        raise ResourceNotFound()
    return wrap_app(app)


def get_app(domain, app_id, wrap_cls=None, latest=False, target=None):
    """
    Utility for getting an app, making sure it's in the domain specified, and
    wrapping it in the right class (Application or RemoteApp).

    'target' is only used if latest=True.  It should be set to one of:
       'build', 'release', or 'save'

    Here are some common usages and the simpler dbaccessor alternatives:
        current_app = get_app(domain, app_id)
                    = get_current_app(domain, app_id)
        latest_released_build = get_app(domain, app_id, latest=True)
                              = get_latest_released_app_doc(domain, app_id)
        latest_build = get_app(domain, app_id, latest=True, target='build')
                     = get_latest_build_doc(domain, app_id)
    Use wrap_app() if you need the wrapped object.
    """
    from .models import Application
    if not app_id:
        raise Http404()
    try:
        app = Application.get_db().get(app_id)
    except ResourceNotFound:
        raise Http404()

    if latest:
        if not domain:
            domain = app['domain']

        if app.get('copy_of'):
            # The id passed in corresponds to a build
            app_id = app.get('copy_of')

        if target == 'build':
            app = get_latest_build_doc(domain, app_id) or app
        elif target == 'save':
            pass  # just use the working copy of the app
        else:
            app = get_latest_released_app_doc(domain, app_id) or app

    if domain and app['domain'] != domain:
        raise Http404()
    try:
        return wrap_app(app, wrap_cls=wrap_cls)
    except DocTypeError:
        raise Http404()


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


def get_built_app_ids_with_submissions_for_app_id(domain, app_id, version=None):
    """
    Returns all the built apps for an application id that have submissions.
    If version is specified returns all apps after that version.
    """
    from .models import Application
    key = [domain, app_id]
    skip = 1 if version else 0
    results = Application.get_db().view(
        'apps_with_submissions/view',
        startkey=key + [version],
        endkey=key + [{}],
        reduce=False,
        include_docs=False,
        skip=skip
    ).all()
    return [result['id'] for result in results]


def get_latest_app_ids_and_versions(domain, app_id=None):
    """
    Returns all the latest app_ids and versions in a dictionary.
    :param domain: The domain to get the app from
    :param app_id: The app_id to get the latest version from. If not specified gets latest versions of all
        apps in the domain
    :returns: {app_id: latest_version}
    """
    from .models import Application
    key = [domain]

    results = Application.get_db().view(
        'app_manager/applications_brief',
        startkey=key + [{}],
        endkey=key,
        descending=True,
        reduce=False,
        include_docs=True,
    ).all()

    latest_ids_and_versions = {}
    if app_id:
        results = filter(lambda r: r['value']['_id'] == app_id, results)
    for result in results:
        app_id = result['value']['_id']
        version = result['value']['version']

        # Since we have sorted, we know the first instance is the latest version
        if app_id not in latest_ids_and_versions:
            latest_ids_and_versions[app_id] = version

    return latest_ids_and_versions


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


def get_all_app_ids(domain):
    """
    Returns a list of all the app_ids ever built and current Applications.
    """
    from .models import Application
    results = Application.get_db().view(
        'app_manager/saved_app',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
    ).all()
    return [result['id'] for result in results]


def get_all_built_app_ids_and_versions(domain):
    """
    Returns a list of all the app_ids ever built and their version.
    [[AppBuildVersion(app_id, build_id, version)], ...]
    """
    from .models import Application
    results = Application.get_db().view(
        'app_manager/saved_app',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
    ).all()
    return map(lambda result: AppBuildVersion(
        app_id=result['key'][1],
        build_id=result['id'],
        version=result['key'][2],
    ), results)


def get_case_types_from_apps(domain):
    """
    Get the case types of modules in applications in the domain.
    :returns: A set of case_types
    """
    q = (AppES()
         .domain(domain)
         .size(0)
         .terms_aggregation('modules.case_type.exact', 'case_types'))
    return set(q.run().aggregations.case_types.keys)


def get_case_sharing_apps_in_domain(domain, exclude_app_id=None):
    apps = get_apps_in_domain(domain, include_remote=False)
    return [a for a in apps if a.case_sharing and exclude_app_id != a.id]
