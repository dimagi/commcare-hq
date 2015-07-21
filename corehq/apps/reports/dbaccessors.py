import json
import settings
from corehq.apps.reports.models import HQExportSchema


def get_exports(domain):
    # add saved exports. because of the way in which the key is stored
    # (serialized json) this is a little bit hacky, but works.
    startkey = json.dumps([domain, ""])[:-3]
    endkey = "%s{" % startkey
    return HQExportSchema.view(
        "couchexport/saved_export_schemas",
        startkey=startkey,
        endkey=endkey,
        include_docs=True,
        stale=settings.COUCH_STALE_QUERY,
    )
