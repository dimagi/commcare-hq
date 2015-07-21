import json
import settings
from corehq.apps.reports.models import HQExportSchema


def stale_get_exports(domain, include_docs=True, **kwargs):
    # add saved exports. because of the way in which the key is stored
    # (serialized json) this is a little bit hacky, but works.
    startkey = json.dumps([domain, ""])[:-3]
    endkey = "%s{" % startkey
    return HQExportSchema.view(
        "couchexport/saved_export_schemas",
        startkey=startkey,
        endkey=endkey,
        include_docs=include_docs,
        stale=settings.COUCH_STALE_QUERY,
        **kwargs
    )
