from corehq.util.couch import stale_ok


def update_analytics_indexes():
    from .models import Application
    Application.get_db().view('exports_forms/by_xmlns', limit=1).all()


def get_exports_by_application(domain):
    from .models import Application
    return Application.get_db().view(
        'exports_forms/by_xmlns',
        startkey=['^Application', domain],
        endkey=['^Application', domain, {}],
        reduce=False,
        stale=stale_ok(),
    ).all()
