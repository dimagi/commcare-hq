from .models import Application


def domain_has_apps(domain):
    results = Application.get_db().view('app_manager/applications_brief',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        limit=1,
    ).all()
    return len(results) > 0


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

    view_results = Application.get_db().view(view_name,
        startkey=startkey,
        endkey=endkey,
        include_docs=True,
    )

    remote_app_filter = None if include_remote else lambda app: not app.is_remote_app()
    wrapped_apps = [get_correct_app_class(row['doc']).wrap(row['doc']) for row in view_results]
    return filter(remote_app_filter, wrapped_apps)
