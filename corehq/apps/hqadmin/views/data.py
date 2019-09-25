import json
from collections import OrderedDict, defaultdict, namedtuple

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render

import six.moves.html_parser
from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.locations.models import SQLLocation
from corehq.elastic import ES_META, run_query
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.form_processor.serializers import (
    CommCareCaseSQLRawDocSerializer,
    XFormInstanceSQLRawDocSerializer,
)
from corehq.util import reverse
from corehq.util.couchdb_management import couch_config
from corehq.util.json import CommCareJSONEncoder


class _DbWrapper(object):
    def __init__(self, dbname, doc_type):
        self.dbname = dbname
        self.doc_type = doc_type

    def get(self, record_id):
        raise NotImplementedError

    def get_context(self, record_id):
        doc = self.get(record_id)
        return {
            "doc": json.dumps(doc, indent=4, sort_keys=True, cls=CommCareJSONEncoder),
            "doc_type": doc.get('doc_type', self.doc_type),
            "domain": doc.get('domain', 'Unknown'),
            "dbname": self.dbname,
        }


class _CouchDb(_DbWrapper):
    """
    Light wrapper for providing interface like Couchdbkit's Database objects.
    """

    def __init__(self, db):
        self.db = db
        super(_CouchDb, self).__init__(db.dbname, getattr(db, 'doc_type', 'Unknown'))

    def get(self, record_id):
        return self.db.get(record_id)


class _SQLDb(_DbWrapper):
    def __init__(self, dbname, getter, doc_type):
        self._getter = getter
        super(_SQLDb, self).__init__(dbname, doc_type)

    def get(self, record_id):
        try:
            return self._getter(record_id)
        except (XFormNotFound, CaseNotFound, ObjectDoesNotExist):
            raise ResourceNotFound("missing")


@memoized
def get_databases():
    sql_dbs = [
        _SQLDb(
            XFormInstanceSQL._meta.db_table,
            lambda id_: XFormInstanceSQLRawDocSerializer(XFormInstanceSQL.get_obj_by_id(id_)).data,
            XFormInstanceSQL.__name__
        ),
        _SQLDb(
            CommCareCaseSQL._meta.db_table,
            lambda id_: CommCareCaseSQLRawDocSerializer(CommCareCaseSQL.get_obj_by_id(id_)).data,
            CommCareCaseSQL.__name__
        ),
        _SQLDb(
            SQLLocation._meta.db_table,
            lambda id_: SQLLocation.objects.get(location_id=id_).to_json(),
            SQLLocation.__name__
        ),
    ]

    all_dbs = OrderedDict()
    all_dbs['commcarehq'] = None  # make this DB first in list
    couchdbs_by_name = couch_config.all_dbs_by_db_name
    for dbname in sorted(couchdbs_by_name):
        all_dbs[dbname] = _CouchDb(couchdbs_by_name[dbname])
    for db in sql_dbs:
        all_dbs[db.dbname] = db
    return all_dbs


def get_db_from_db_name(db_name):
    all_dbs = get_databases()
    if db_name in all_dbs:
        return all_dbs[db_name]
    else:
        return _CouchDb(couch_config.get_db(db_name))


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
        dbs = list(get_databases().values())

    db_results = []
    for db in dbs:
        try:
            response.update(db.get_context(doc_id))
        except ResourceNotFound as e:
            db_results.append(db_result(db.dbname, str(e), STATUSES[str(e)]))
        else:
            db_results.append(db_result(db.dbname, 'found', 'success'))

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

    context['all_databases'] = [db for db in get_databases()]
    return render(request, "hqadmin/raw_doc.html", context)
