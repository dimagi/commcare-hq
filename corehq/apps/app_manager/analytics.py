from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.couch import stale_ok


def update_analytics_indexes():
    from .models import Application
    Application.get_db().view('exports_forms_by_app/view', limit=1).all()


def get_exports_by_application(domain):
    from .models import Application
    return Application.get_db().view(
        'exports_forms_by_app/view',
        startkey=[domain, {}],
        endkey=[domain, {}, {}],
        reduce=False,
        stale=stale_ok(),
    ).all()
