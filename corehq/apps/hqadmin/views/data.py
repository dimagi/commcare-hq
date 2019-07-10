from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import json
from collections import OrderedDict, defaultdict, namedtuple

import six
import six.moves.html_parser
from couchdbkit import ResourceNotFound
from django.core.exceptions import ObjectDoesNotExist
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
)
from django.shortcuts import render

from corehq.apps.domain.decorators import (
    require_superuser)
from corehq.apps.locations.models import SQLLocation
from corehq.elastic import ES_META, run_query
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.serializers import XFormInstanceSQLRawDocSerializer, \
    CommCareCaseSQLRawDocSerializer
from corehq.util import reverse
from corehq.util.couchdb_management import couch_config
from corehq.util.json import CommCareJSONEncoder


class _Db(object):
    """
    Light wrapper for providing interface like Couchdbkit's Database objects.
    """

    def __init__(self, dbname, getter, doc_type):
        self.dbname = dbname
        self._getter = getter
        self.doc_type = doc_type

    def get(self, record_id):
        try:
            return self._getter(record_id)
        except (XFormNotFound, CaseNotFound, ObjectDoesNotExist):
            raise ResourceNotFound("missing")


_SQL_DBS = OrderedDict((db.dbname, db) for db in [
    _Db(
        XFormInstanceSQL._meta.db_table,
        lambda id_: XFormInstanceSQLRawDocSerializer(XFormInstanceSQL.get_obj_by_id(id_)).data,
        XFormInstanceSQL.__name__
    ),
    _Db(
        CommCareCaseSQL._meta.db_table,
        lambda id_: CommCareCaseSQLRawDocSerializer(CommCareCaseSQL.get_obj_by_id(id_)).data,
        CommCareCaseSQL.__name__
    ),
    _Db(
        SQLLocation._meta.db_table,
        lambda id_: SQLLocation.objects.get(location_id=id_).to_json(),
        SQLLocation.__name__
    ),
])


def get_db_from_db_name(db_name):
    if db_name in _SQL_DBS:
        return _SQL_DBS[db_name]
    elif db_name == couch_config.get_db(None).dbname:  # primary db
        return couch_config.get_db(None)
    else:
        return couch_config.get_db(db_name)


def _lookup_id_in_database(doc_id, db_name=None):
    db_result = namedtuple('db_result', 'dbname result status')
    STATUSES = defaultdict(lambda: 'warning', {
        'missing': 'default',
        'deleted': 'danger',
    })

    response = {"doc_id": doc_id}
    if db_name:
        dbs = [get_db_from_db_name(db_name)]
        response['selected_db'] = db_name
    else:
        couch_dbs = list(couch_config.all_dbs_by_slug.values())
        sql_dbs = list(_SQL_DBS.values())
        dbs = couch_dbs + sql_dbs

    db_results = []
    for db in dbs:
        try:
            doc = db.get(doc_id)
        except ResourceNotFound as e:
            db_results.append(db_result(db.dbname, six.text_type(e), STATUSES[six.text_type(e)]))
        else:
            db_results.append(db_result(db.dbname, 'found', 'success'))
            response.update({
                "doc": json.dumps(doc, indent=4, sort_keys=True, cls=CommCareJSONEncoder),
                "doc_type": doc.get('doc_type', getattr(db, 'doc_type', 'Unknown')),
                "domain": doc.get('domain', 'Unknown'),
                "dbname": db.dbname,
            })

    response['db_results'] = db_results
    return response


@require_superuser
def doc_in_es(request):
    doc_id = request.GET.get("id")
    if not doc_id:
        return render(request, "hqadmin/doc_in_es.html", {})

    def to_json(doc):
        return json.dumps(doc, indent=4, sort_keys=True) if doc else "NOT FOUND!"

    query = {"filter": {"ids": {"values": [doc_id]}}}
    found_indices = {}
    es_doc_type = None
    for index in ES_META:
        res = run_query(index, query)
        if 'hits' in res and res['hits']['total'] == 1:
            es_doc = res['hits']['hits'][0]['_source']
            found_indices[index] = to_json(es_doc)
            es_doc_type = es_doc_type or es_doc.get('doc_type')

    context = {
        "doc_id": doc_id,
        "es_info": {
            "status": "found" if found_indices else "NOT FOUND IN ELASTICSEARCH!",
            "doc_type": es_doc_type,
            "found_indices": found_indices,
        },
        "couch_info": _lookup_id_in_database(doc_id),
    }
    return render(request, "hqadmin/doc_in_es.html", context)


@require_superuser
def raw_doc(request):
    doc_id = request.GET.get("id")
    db_name = request.GET.get("db_name", None)
    if db_name and "__" in db_name:
        db_name = db_name.split("__")[-1]
    context = _lookup_id_in_database(doc_id, db_name) if doc_id else {}

    if request.GET.get("raw", False):
        if 'doc' in context:
            return HttpResponse(context['doc'], content_type="application/json")
        else:
            return HttpResponse(json.dumps({"status": "missing"}),
                                content_type="application/json", status=404)

    other_couch_dbs = sorted([_f for _f in couch_config.all_dbs_by_slug if _f])
    context['all_databases'] = ['commcarehq'] + other_couch_dbs + list(_SQL_DBS)
    return render(request, "hqadmin/raw_doc.html", context)
