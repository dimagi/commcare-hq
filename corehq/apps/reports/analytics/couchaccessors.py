from corehq.util.couch import stale_ok
from couchforms.models import XFormInstance
from dimagi.utils.couch.cache import cache_core


def guess_form_name_from_submissions_using_xmlns(domain, xmlns):
    key = ["xmlns", domain, xmlns]
    results = cache_core.cached_view(
        XFormInstance.get_db(),
        'reports_forms/name_by_xmlns',
        reduce=False,
        startkey=key,
        endkey=key + [{}],
        limit=1,
        stale=stale_ok(),
        cache_expire=60
    )
    try:
        data = list(results)[0]
        return data['value']
    except IndexError:
        return None
