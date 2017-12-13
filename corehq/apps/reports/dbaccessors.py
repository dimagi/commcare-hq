from __future__ import absolute_import
import json

from django.conf import settings

from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class


def _get_exports(domain, include_docs=True, reduce=False, **kwargs):
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
        reduce=reduce,
        **kwargs
    )


def get_exports_json(domain):
    for res in _get_exports(domain):
        # workaround for http://manage.dimagi.com/default.asp?223471
        if res['doc'] is not None:
            yield res['doc']


def stale_get_exports_json(domain):
    for res in _get_exports(domain, stale=settings.COUCH_STALE_QUERY):
        # workaround for http://manage.dimagi.com/default.asp?223471
        if res['doc'] is not None:
            yield res['doc']


def stale_get_export_count(domain):
    result = _get_exports(
        domain,
        include_docs=False,
        limit=1,
        reduce=True,
    ).one()
    return result["value"] if result else 0


def touch_exports(domain):
    _get_exports(domain, include_docs=False, limit=1).fetch()


def hq_group_export_configs_by_domain(domain):
    from corehq.apps.reports.models import HQGroupExportConfiguration
    return get_docs_in_domain_by_class(domain, HQGroupExportConfiguration)
