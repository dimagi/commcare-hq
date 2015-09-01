import json
import settings
from corehq.apps.reports.models import HQExportSchema


def get_exports(domain, include_docs=True, limit=None, stale=False):
    # add saved exports. because of the way in which the key is stored
    # (serialized json) this is a little bit hacky, but works.
    startkey = json.dumps([domain, ""])[:-3]
    endkey = "%s{" % startkey

    kwargs = {}
    if limit is not None:
        kwargs['limit'] = limit
    if stale:
        kwargs['stale'] = settings.COUCH_STALE_QUERY
    return HQExportSchema.view(
        "couchexport/saved_export_schemas",
        startkey=startkey,
        endkey=endkey,
        include_docs=include_docs,
        **kwargs
    )


def stale_get_exports(domain, include_docs=True, limit=None):
    return get_exports(
        domain,
        include_docs=include_docs,
        stale=True,
        limit=limit,
    )


def touch_exports(domain):
    get_exports(domain, include_docs=False, limit=1).fetch()
