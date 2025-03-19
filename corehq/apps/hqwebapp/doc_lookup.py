from collections import OrderedDict, defaultdict, namedtuple
from uuid import UUID

import attr
from couchdbkit import ResourceNotFound
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.python import Serializer
from memoized import memoized

from corehq.apps.locations.models import SQLLocation
from corehq.apps.fixtures.models import LookupTable, LookupTableRow
from corehq.apps.sms.models import SMS, SQLMobileBackend
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.serializers import (
    CommCareCaseRawDocSerializer,
    XFormInstanceRawDocSerializer,
)
from corehq.util.couchdb_management import couch_config

DbResult = namedtuple('DbResult', 'dbname result status')


@attr.s
class LookupResult:
    doc_id = attr.ib()
    doc = attr.ib()
    doc_type = attr.ib()
    domain = attr.ib()
    dbname = attr.ib()
    data_serializer = attr.ib()

    def asdict(self):
        res = attr.asdict(self)
        res.pop("data_serializer")
        return res

    def get_serialized_doc(self):
        if not self.data_serializer:
            return self.doc
        return self.data_serializer(self.doc)


def lookup_doc_id(doc_id):
    """Look up a document ID

    :param doc_id: ID of document to look for
    :returns: LookupResult or None
    """
    if doc_id is None:
        raise TypeError('`doc_id` is NoneType, expected str.')
    result, _ = lookup_id_in_databases(doc_id, get_databases().values())
    return result


def lookup_id_in_databases(doc_id, dbs, find_first=True):
    """Look up a document ID

    :param doc_id: ID of document to look for
    :param dbs: list of databases to look in
    :param find_first: Set to False to look in all databases even after a match is found.
    :returns: Tuple of (LookupResult or None, list of DbResult objects for each DB searched)
    """
    STATUSES = defaultdict(lambda: 'warning', {
        'missing': 'default',
        'deleted': 'danger',
    })

    db_results = []
    response = None
    for db in dbs:
        try:
            db_response = db.get_context(doc_id)
            if not response:
                response = db_response
        except ResourceNotFound as e:
            db_results.append(DbResult(db.dbname, str(e), STATUSES[str(e)]))
        else:
            db_results.append(DbResult(db.dbname, 'found', 'success'))
            if find_first:
                break

    return response, db_results


@memoized
def get_databases():
    """Return an ordered dict of (dbname: database). The order is
    according to search preference, the first DB to contain a document
    should be assumed to be the authoritative one."""
    sql_dbs = [
        _SQLDb(
            XFormInstance._meta.db_table,
            lambda id_: XFormInstance.get_obj_by_id(id_),
            "XFormInstance",
            lambda doc: XFormInstanceRawDocSerializer(doc).data,
        ),
        _SQLDb(
            CommCareCase._meta.db_table,
            lambda id_: CommCareCase.get_obj_by_id(id_),
            "CommCareCase",
            lambda doc: CommCareCaseRawDocSerializer(doc).data,
        ),
        _SQLDb(
            SQLLocation._meta.db_table,
            lambda id_: SQLLocation.objects.get(location_id=id_),
            'Location',
            lambda doc: doc.to_json()
        ),
        _SQLDb(
            SMS._meta.db_table,
            lambda id_: SMS.objects.get(couch_id=id_),
            'SMS',
            lambda doc: doc.to_json()
        ),
        _SQLDb(
            SQLMobileBackend._meta.db_table,
            lambda id_: SQLMobileBackend.objects.get(couch_id=id_),
            'SQLMobileBackend',
            lambda doc: doc.to_json()
        ),
        _SQLDb(
            LookupTable._meta.db_table,
            make_uuid_getter(LookupTable),
            'LookupTable',
        ),
        _SQLDb(
            LookupTableRow._meta.db_table,
            make_uuid_getter(LookupTableRow),
            'LookupTableRow',
        ),
    ]

    all_dbs = OrderedDict()
    for db in sql_dbs:
        all_dbs[db.dbname] = db
    couchdbs_by_name = couch_config.all_dbs_by_db_name
    for dbname in sorted(couchdbs_by_name):
        all_dbs[dbname] = _CouchDb(couchdbs_by_name[dbname])
    return all_dbs


def get_db_from_db_name(db_name):
    all_dbs = get_databases()
    if db_name in all_dbs:
        return all_dbs[db_name]
    else:
        return _CouchDb(couch_config.get_db(db_name))


class _DbWrapper(object):
    def __init__(self, dbname, doc_type, serializer):
        self.dbname = dbname
        self.doc_type = doc_type
        self.serializer = serializer

    def get(self, record_id):
        raise NotImplementedError

    def get_context(self, record_id):
        doc = self.get(record_id)
        return self._context_for_doc(record_id, doc)

    def _context_for_doc(self, doc_id, doc):

        if isinstance(doc, dict):
            doc_type = doc.get('doc_type', self.doc_type)
            domain = doc.get('domain', 'Unknown')
        else:
            doc_type = self.doc_type
            domain = getattr(doc, 'domain', 'Unknown')

        return LookupResult(
            doc_id=doc_id,
            doc=doc,
            doc_type=doc_type,
            domain=domain,
            dbname=self.dbname,
            data_serializer=self.serializer
        )


class _CouchDb(_DbWrapper):
    """
    Light wrapper for providing interface like Couchdbkit's Database objects.
    """

    def __init__(self, db):
        self.db = db
        doc_type = getattr(db, 'doc_type', 'Unknown')
        super(_CouchDb, self).__init__(db.dbname, doc_type, None)

    def get(self, record_id):
        return self.db.get(record_id)


def model_to_json(obj):
    return Serializer().serialize([obj])[0]


class _SQLDb(_DbWrapper):
    def __init__(self, dbname, getter, doc_type, serializer=model_to_json):
        self._getter = getter
        super(_SQLDb, self).__init__(dbname, doc_type, serializer)

    def get(self, record_id):
        try:
            return self._getter(record_id)
        except (XFormNotFound, CaseNotFound, ObjectDoesNotExist):
            raise ResourceNotFound("missing")


def make_uuid_getter(model, id_field="id"):
    def getter(id_):
        try:
            id_value = UUID(id_)
        except ValueError:
            raise model.DoesNotExist
        return model.objects.get(**{id_field: id_value})
    return getter
