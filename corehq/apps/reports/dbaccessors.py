import json
from django.conf import settings


def _get_exports(domain, include_docs=True, **kwargs):
    from corehq.apps.reports.models import HQExportSchema
    # add saved exports. because of the way in which the key is stored
    # (serialized json) this is a little bit hacky, but works.
    startkey = json.dumps([domain, ""])[:-3]
    endkey = "%s{" % startkey
    return HQExportSchema.get_db().view(
        "couchexport/saved_export_schemas",
        startkey=startkey,
        endkey=endkey,
        include_docs=include_docs,
        **kwargs
    )


def stale_get_exports_json(domain):
    for res in _get_exports(domain, stale=settings.COUCH_STALE_QUERY):
        yield res['doc']


def stale_get_export_count(domain):
    return _get_exports(
        domain,
        stale=settings.COUCH_STALE_QUERY,
        include_docs=False,
        limit=1
    ).count()


def touch_exports(domain):
    _get_exports(domain, include_docs=False, limit=1).fetch()
