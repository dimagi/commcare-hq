import json
import settings
from corehq.apps.reports.models import HQExportSchema


def get_exports(domain, include_docs=True, **kwargs):
    # add saved exports. because of the way in which the key is stored
    # (serialized json) this is a little bit hacky, but works.
    startkey = json.dumps([domain, ""])[:-3]
    endkey = "%s{" % startkey
    return HQExportSchema.view(
        "couchexport/saved_export_schemas",
        startkey=startkey,
        endkey=endkey,
        include_docs=include_docs,
        **kwargs
    )


def stale_get_exports(domain, include_docs=True, **kwargs):
    return get_exports(
        domain,
        include_docs=include_docs,
        stale=settings.COUCH_STALE_QUERY,
        **kwargs
    )


def touch_exports(domain):
    get_exports(domain, include_docs=False, limit=1).fetch()
