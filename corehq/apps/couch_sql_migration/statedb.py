import errno
import json
import logging
import os
import os.path
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from itertools import groupby

import attr
from memoized import memoized
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    and_,
    bindparam,
    func,
    or_,
)
from sqlalchemy.exc import IntegrityError

from dimagi.utils.chunked import chunked

from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.tzmigration.planning import Base, DiffDB, PlanningDiff as Diff
from corehq.apps.tzmigration.timezonemigration import MISSING, json_diff
from corehq.util.log import with_progress_bar
from corehq.util.metrics import metrics_counter

from .diff import filter_form_diffs

log = logging.getLogger(__name__)


def init_state_db(domain, state_dir):
    db_filepath = _get_state_db_filepath(domain, state_dir)
    db_dir = os.path.dirname(db_filepath)
    if os.path.isdir(state_dir) and not os.path.isdir(db_dir):
        os.mkdir(db_dir)
    return StateDB.init(domain, db_filepath)


def open_state_db(domain, state_dir, *, readonly=True):
    """Open state db in read-only mode"""
    db_filepath = _get_state_db_filepath(domain, state_dir)
    if not os.path.exists(db_filepath):
        raise Error(f"not found: {db_filepath}")
    return StateDB.open(domain, db_filepath, readonly=readonly)


def delete_state_db(domain, state_dir):
    db_filepath = _get_state_db_filepath(domain, state_dir)
    try:
        os.remove(db_filepath)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def _get_state_db_filepath(domain, state_dir):
    return os.path.join(state_dir, "db", '{}-couch-sql.db'.format(domain))


class StateDB(DiffDB):

    @classmethod
    def init(cls, domain, path):
        is_new_db = not os.path.exists(path)
        db = super(StateDB, cls).init(domain, path)
        if is_new_db:
            db._set_kv("db_unique_id", datetime.utcnow().strftime("%Y%m%d-%H%M%S.%f"))
        else:
            db._migrate()
        return db

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.is_rebuild = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        self.engine.dispose()

    @contextmanager
    def session(self, session=None):
        if session is not None:
            yield session
            return
        session = self.Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    @property
    @memoized
    def unique_id(self):
        with self.session() as session:
            return self._get_kv("db_unique_id", session).value

    def get(self, name, default=None):
        with self.session() as session:
            kv = self._get_kv(f"kv-{name}", session)
            if kv is None:
                return default
            return json.loads(kv.value)

    def set(self, name, value):
        self._upsert(KeyValue, KeyValue.key, f"kv-{name}", json.dumps(value))

    def update_cases(self, case_records):
        """Update case total and processed form counts

        :param case_records: iterable of objects, each having the attributes:

            - id: case id
            - total_forms: number of forms known to update the case.
            - processed_forms: number of forms updating the case that
              have been processed.

        :returns: list of three-tuples `(case_id, total_forms, processed_forms)`
        """
        params = [
            {"case": rec.id, "total": rec.total_forms, "proc": rec.processed_forms}
            for rec in case_records
        ]
        with self.session() as session:
            session.execute(
                """
                REPLACE INTO {table} (case_id, total_forms, processed_forms)
                VALUES (
                    :case,
                    MAX(COALESCE((
                        SELECT total_forms
                        FROM {table}
                        WHERE case_id = :case
                    ), 0), :total),
                    COALESCE((
                        SELECT processed_forms
                        FROM {table}
                        WHERE case_id = :case
                    ), 0) + :proc
                )
                """.format(table=CaseForms.__tablename__),
                params,
            )
            case_ids = [p["case"] for p in params]
            query = session.query(CaseForms).filter(CaseForms.case_id.in_(case_ids))
            result = [(c.case_id, c.total_forms, c.processed_forms) for c in query]
        assert len(case_ids) == len(result), (case_ids, result)
        return result

    def add_processed_forms(self, cases):
        """Increment processed forms count for each of the given cases

        :param cases: dict `{<case_id>: <processed_form_count>, ...}`
        :returns: list of three-tuples `(case_id, total_forms, processed_forms)`
        where `total_forms` is `None` for unknown cases.
        """
        case_col = CaseForms.case_id
        proc_col = CaseForms.processed_forms
        params = [{"case": c, "proc": p} for c, p in cases.items()]
        with self.session() as session:
            session.execute(
                CaseForms.__table__.update()
                .where(case_col == bindparam("case"))
                .values({proc_col: proc_col + bindparam("proc")}),
                params,
            )
            query = session.query(CaseForms).filter(case_col.in_(cases))
            case_forms = {cf.case_id: cf for cf in query}

            def make_result(case_id):
                case = case_forms.get(case_id)
                if case is None:
                    return (case_id, None, None)
                return (case_id, case.total_forms, case.processed_forms)

            return [make_result(case_id) for case_id in cases]

    def iter_cases_with_unprocessed_forms(self):
        query = self.Session().query(
            CaseForms.case_id,
            CaseForms.total_forms,
        ).filter(CaseForms.total_forms > CaseForms.processed_forms)
        for case_id, total_forms in iter_large(query, CaseForms.case_id):
            yield case_id, total_forms

    def get_forms_count(self, case_id):
        with self.session() as session:
            query = session.query(CaseForms.total_forms).filter_by(case_id=case_id)
            return query.scalar() or 0

    def add_cases_to_diff(self, case_ids, *, session=None):
        if not case_ids:
            return
        with self.session(session) as session:
            session.execute(
                f"INSERT OR IGNORE INTO {CaseToDiff.__tablename__} (id) VALUES (:id)",
                [{"id": x} for x in case_ids],
            )

    def add_diffed_cases(self, case_ids):
        if not case_ids:
            return
        with self.session() as session:
            session.execute(
                f"INSERT OR IGNORE INTO {DiffedCase.__tablename__} (id) VALUES (:id)",
                [{"id": x} for x in case_ids],
            )
            (
                session.query(CaseToDiff)
                .filter(CaseToDiff.id.in_(case_ids))
                .delete(synchronize_session=False)
            )

    def iter_undiffed_case_ids(self):
        query = self.Session().query(CaseToDiff.id)
        for case_id, in iter_large(query, CaseToDiff.id):
            yield case_id

    def count_undiffed_cases(self):
        with self.session() as session:
            return session.query(CaseToDiff).count()

    def iter_case_ids_with_diffs(self, changes=False):
        model = DocChanges if changes else DocDiffs
        query = (
            self.Session().query(model.doc_id)
            .filter(model.kind == "CommCareCase")
        )
        for doc_id, in iter_large(query, model.doc_id):
            yield doc_id

    def count_case_ids_with_diffs(self, changes=False):
        model = DocChanges if changes else DocDiffs
        with self.session() as session:
            return (
                session.query(model.doc_id)
                .filter(model.kind == "CommCareCase")
                .count()
            )

    def add_patched_cases(self, case_ids):
        if not case_ids:
            return
        with self.session() as session:
            self.add_cases_to_diff(case_ids, session=session)
            session.execute(
                f"INSERT OR IGNORE INTO {PatchedCase.__tablename__} (id) VALUES (:id)",
                [{"id": x} for x in case_ids],
            )

    def iter_patched_case_ids(self):
        query = self.Session().query(PatchedCase.id)
        for case_id, in iter_large(query, PatchedCase.id):
            yield case_id

    def add_problem_form(self, form_id):
        """Add form to be migrated with "unprocessed" forms

        A "problem" form is an error form with normal doctype (XFormInstance)
        """
        with self.session() as session:
            session.add(ProblemForm(id=form_id))

    def iter_problem_forms(self):
        query = self.Session().query(ProblemForm.id)
        for form_id, in iter_large(query, ProblemForm.id):
            yield form_id

    def add_no_action_case_form(self, form_id):
        try:
            with self.session() as session:
                session.add(NoActionCaseForm(id=form_id))
        except IntegrityError:
            pass
        else:
            self.get_no_action_case_forms.reset_cache(self)

    @memoized
    def get_no_action_case_forms(self):
        """Get the set of form ids that touch cases without actions"""
        return {x for x, in self.Session().query(NoActionCaseForm.id)}

    def set_resume_state(self, key, value):
        resume_key = "resume-{}".format(key)
        self._upsert(KeyValue, KeyValue.key, resume_key, json.dumps(value))

    @contextmanager
    def pop_resume_state(self, key, default):
        resume_key = "resume-{}".format(key)
        with self.session() as session:
            kv = self._get_kv(resume_key, session)
            if kv is None:
                self._set_kv(resume_key, RESUME_NOT_ALLOWED, session)
                yield default
            elif self.is_rebuild:
                yield default
            elif kv.value == RESUME_NOT_ALLOWED:
                raise ResumeError("previous session did not save resume state")
            else:
                yield json.loads(kv.value)
                kv.value = RESUME_NOT_ALLOWED

    def _get_kv(self, key, session):
        return session.query(KeyValue).get(key)

    def _set_kv(self, key, value, session=None):
        with self.session(session) as session:
            session.add(KeyValue(key=key, value=value))

    def _upsert(self, model, key_field, key, value, incr=False):
        with self.session() as session:
            updated = (
                session.query(model)
                .filter(key_field == key)
                .update(
                    {model.value: (model.value + value) if incr else value},
                    synchronize_session=False,
                )
            )
            if not updated:
                obj = model(value=value)
                key_field.__set__(obj, key)
                session.add(obj)
            else:
                assert updated == 1, (key, updated)

    def add_missing_docs(self, kind, doc_ids):
        with self.session() as session:
            session.bulk_save_objects([
                MissingDoc(kind=kind, doc_id=doc_id)
                for doc_id in doc_ids
            ])

    def delete_missing_docs(self, kind):
        with self.session() as session:
            (
                session.query(MissingDoc)
                .filter_by(kind=kind)
                .delete(synchronize_session=False)
            )

    def doc_not_missing(self, kind, doc_id):
        with self.session() as session:
            (
                session.query(MissingDoc.doc_id)
                .filter_by(kind=kind, doc_id=doc_id)
                .delete(synchronize_session=False)
            )

    def save_form_diffs(self, couch_json, sql_json):
        diffs = json_diff(couch_json, sql_json, track_list_indices=False)
        diffs = filter_form_diffs(couch_json, sql_json, diffs)
        dd_count = partial(metrics_counter, tags={"domain": self.domain})
        dd_count("commcare.couchsqlmigration.form.diffed")
        doc_type = couch_json["doc_type"]
        doc_id = couch_json["_id"]
        self.add_diffs(doc_type, doc_id, diffs)
        if diffs:
            dd_count("commcare.couchsqlmigration.form.has_diff")

    def replace_case_diffs(self, case_diffs, **kw):
        diffs_by_doc = defaultdict(list)
        for kind, doc_id, diffs in case_diffs:
            assert all(isinstance(d.path, (list, tuple)) for d in diffs), diffs
            if kind == "stock state":
                case_id = doc_id.split("/", 1)[0]
                diffs = [
                    d._replace(path={"stock_id": doc_id, "path": d.path})
                    for d in diffs
                ]
                diffs_by_doc[("CommCareCase", case_id)].extend(diffs)
            else:
                diffs_by_doc[(kind, doc_id)].extend(diffs)
        for (doc_type, case_id), diffs in diffs_by_doc.items():
            self.add_diffs(doc_type, case_id, diffs, **kw)

    def add_diffs(self, kind, doc_id, diffs, *, session=None, _model=None):
        if _model is None:
            _model = DocDiffs
        to_dict = _model.diff_to_dict
        assert kind != "stock state", ("stock state diffs should be "
            "combined with other diffs for the same case")
        if diffs:
            diff_json = json.dumps([to_dict(d) for d in diffs], cls=LazyEncoder)
            with self.session(session) as session:
                session.execute(
                    f"""
                    REPLACE INTO {_model.__tablename__} (kind, doc_id, diffs)
                    VALUES (:kind, :doc_id, :diffs)
                    """,
                    [{"kind": kind, "doc_id": doc_id, "diffs": diff_json}],
                )
        else:
            with self.session(session) as session:
                session.query(_model).filter(
                    _model.kind == kind,
                    _model.doc_id == doc_id,
                ).delete(synchronize_session=False)

    def replace_case_changes(self, changes):
        self.replace_case_diffs(changes, _model=DocChanges)

    def add_changes(self, *args):
        self.add_diffs(*args, _model=DocChanges)

    def iter_diffs(self, *, _model=None):
        if _model is None:
            _model = DocDiffs
        with self.session() as session:
            for kind, in list(session.query(_model.kind).distinct()):
                query = session.query(_model).filter_by(kind=kind)
                for doc in iter_large(query, _model.doc_id):
                    for data in json.loads(doc.diffs):
                        yield _model.dict_to_diff(doc.kind, doc.doc_id, data)

    def iter_changes(self):
        return self.iter_diffs(_model=DocChanges)

    def iter_doc_diffs(self, kind=None, doc_ids=None, by_kind=None, _model=None):
        """Iterate over diffs of the given kind

        "stock state" diffs cannot be queried directly with this method.
        They are grouped with diffs of the corresponding case
        (kind="CommCareCase", doc_id=<case_id>).

        :yeilds: three-tuples `(kind, doc_id, diffs)`. The diffs yielded
        here are `PlanningDiff` objects, which should not be confused
        with json diffs (`<PlanningDiff>.json_diff`).
        """
        if _model is None:
            _model = DocDiffs
        if by_kind is not None:
            assert kind is None, kind
            assert doc_ids is None, doc_ids
            for kind, doc_ids in by_kind.items():
                if not doc_ids:
                    yield from self.iter_doc_diffs(kind, _model=_model)
                else:
                    for chunk in chunked(doc_ids, 500, list):
                        yield from self.iter_doc_diffs(kind, chunk, _model=_model)
            return
        with self.session() as session:
            query = session.query(_model)
            if kind is not None:
                query = query.filter_by(kind=kind)
            if doc_ids is not None:
                query = query.filter(_model.doc_id.in_(doc_ids))
            for doc in iter_large(query, _model.doc_id):
                yield doc.kind, doc.doc_id, [
                    _model.dict_to_diff(doc.kind, doc.doc_id, data)
                    for data in json.loads(doc.diffs)
                ]

    def iter_doc_changes(self, kind=None, **kw):
        return self.iter_doc_diffs(kind, _model=DocChanges, **kw)

    def get_diffs(self):
        """DEPRECATED use iter_diffs(); the result may be very large"""
        return list(self.iter_diffs())

    def set_counter(self, kind, value):
        self._upsert(DocCount, DocCount.kind, kind, value)

    def get_doc_counts(self):
        """Returns a dict of counts by kind

        Values are `Counts` objects having `total` and `missing`
        fields:

        - total: number of items counted with `increment_counter`.
        - missing: count of ids found in Couch but not in SQL.
        - diffs: count of docs with diffs.
        - changes: count of docs with expected changes.
        """
        with self.session() as session:
            totals = {dc.kind: dc.value for dc in session.query(DocCount)}
            diffs = dict(session.query(
                DocDiffs.kind,
                func.count(DocDiffs.doc_id),
            ).group_by(DocDiffs.kind))
            missing = dict(session.query(
                MissingDoc.kind,
                func.count(MissingDoc.doc_id),
            ).group_by(MissingDoc.kind))
            changes = dict(session.query(
                DocChanges.kind,
                func.count(DocChanges.doc_id),
            ).group_by(DocChanges.kind))
        return {kind: Counts(
            total=totals.get(kind, 0),
            diffs=diffs.get(kind, 0),
            missing=missing.get(kind, 0),
            changes=changes.get(kind, 0),
        ) for kind in set(totals) | set(diffs) | set(missing) | set(changes)}

    def iter_missing_doc_ids(self, kind):
        with self.session() as session:
            query = (
                session.query(MissingDoc.doc_id)
                .filter(MissingDoc.kind == kind)
            )
            yield from (x for x, in iter_large(query, MissingDoc.doc_id))

    def get_diff_stats(self):
        raise NotImplementedError("use get_doc_counts")

    def clone_casediff_data_from(self, casediff_state_path):
        """Copy casediff state into this state db

        model analysis
        - CaseForms - casediff r/w
        - Diff - deprecated
        - KeyValue - casediff r/w, main r/w (different keys)
        - DocCount - casediff w, main r
        - DocDiffs - casediff w (case and stock kinds), main r/w
        - DocChanges - casediff w (case and stock kinds), main r/w
        - MissingDoc - casediff w, main r
        - NoActionCaseForm - main r/w
        - PatchedCase - main r/w
        - ProblemForm - main r/w
        """
        def quote(value):
            assert isinstance(value, str) and "'" not in value, repr(value)
            return f"'{value}'"

        def quotelist(values):
            return f"({', '.join(quote(v) for v in values)})"

        def is_id(column):
            return column.key == "id" and isinstance(column.type, Integer)

        def copy(model, session, where_expr=None):
            log.info("copying casediff data: %s", model.__name__)
            where = f"WHERE {where_expr}" if where_expr else ""
            fields = ", ".join(c.key for c in model.__table__.columns if not is_id(c))
            session.execute(f"DELETE FROM main.{model.__tablename__} {where}")
            session.execute(f"""
                INSERT INTO main.{model.__tablename__} ({fields})
                SELECT {fields} FROM cddb.{model.__tablename__} {where}
            """)

        log.info("checking casediff data preconditions...")
        casediff_db = type(self).open(self.domain, casediff_state_path)
        with casediff_db.session() as cddb:
            expect_casediff_kinds = {
                "CommCareCase",
                "CommCareCase-Deleted",
                "stock state",
            }
            casediff_kinds = {k for k, in cddb.query(DocDiffs.kind).distinct()}
            casediff_kinds.update(k for k, in cddb.query(DocChanges.kind).distinct())
            assert not casediff_kinds - expect_casediff_kinds, casediff_kinds

            resume_keys = [
                key for key, in cddb.query(KeyValue.key)
                .filter(KeyValue.key.startswith("resume-"))
            ]
            assert all("Case" in key for key in resume_keys), resume_keys

            count_kinds = [k for k, in cddb.query(DocCount.kind).distinct()]
            assert all("CommCareCase" in k for k in count_kinds), count_kinds

            missing_kinds = [m for m, in cddb.query(MissingDoc.kind).distinct()]
            assert all("CommCareCase" in k for k in missing_kinds), missing_kinds
        casediff_db.close()

        with self.session() as session:
            session.execute(f"ATTACH DATABASE {quote(casediff_state_path)} AS cddb")
            copy(CaseForms, session)
            copy(Diff, session, f"kind IN {quotelist(expect_casediff_kinds)}")
            copy(DocDiffs, session, f"kind IN {quotelist(expect_casediff_kinds)}")
            copy(DocChanges, session, f"kind IN {quotelist(expect_casediff_kinds)}")
            copy(KeyValue, session, f"key IN {quotelist(resume_keys)}")
            copy(DocCount, session)
            copy(MissingDoc, session)

    def _migrate(self):
        with self.session() as session:
            self._migrate_diff_to_docdiffs(session)

    def _migrate_diff_to_docdiffs(self, session):
        if session.query(session.query(DocDiffs).exists()).scalar():
            return  # already migrated
        if not session.query(session.query(Diff).exists()).scalar():
            return  # nothing to migrate
        log.info("migrating PlanningDiff to DocDiffs...")
        base_query = session.query(Diff).filter(Diff.kind != "stock state")
        count = base_query.count()
        query = base_query.order_by(Diff.kind, Diff.doc_id)
        items = with_progress_bar(query, count, oneline="concise", prefix="main diffs")
        for (kind, doc_id), diffs in groupby(items, lambda d: (d.kind, d.doc_id)):
            diffs = [d.json_diff for d in diffs]
            self.add_diffs(kind, doc_id, diffs, session=session)
        # "stock state" diffs must be migrated after "CommCareCase"
        # diffs since it will probably replace some of them
        self._migrate_stock_state_diffs(session)

    def _migrate_stock_state_diffs(self, session):
        def get_case_diffs(case_id):
            case_diffs = session.query(Diff).filter_by(doc_id=case_id)
            return [d.json_diff for d in case_diffs]
        query = session.query(Diff).filter_by(kind="stock state")
        count = query.count()
        stock_state_diffs = with_progress_bar(
            query, count, oneline="concise", prefix="stock state cases")
        diffs_by_doc = defaultdict(list)
        for stock_diff in stock_state_diffs:
            case_id, x, x = stock_diff.doc_id.split("/")
            key = ("CommCareCase", case_id)
            jsdiff = stock_diff.json_diff
            stock_json_diff = jsdiff._replace(path={
                "stock_id": stock_diff.doc_id,
                "path": jsdiff.path,
            })
            if key not in diffs_by_doc:
                diffs_by_doc[key].extend(get_case_diffs(case_id))
            diffs_by_doc[key].append(stock_json_diff)
        for (doc_type, case_id), diffs in diffs_by_doc.items():
            self.add_diffs(doc_type, case_id, diffs, session=session)

    def vacuum(self):
        with self.session() as session:
            session.execute("VACUUM")


class Error(Exception):
    pass


class ResumeError(Exception):
    pass


RESUME_NOT_ALLOWED = "RESUME_NOT_ALLOWED"


class CaseForms(Base):
    __tablename__ = "caseforms"

    case_id = Column(String(50), nullable=False, primary_key=True)
    total_forms = Column(Integer, nullable=False)
    processed_forms = Column(Integer, nullable=False, default=0)


class CaseToDiff(Base):
    __tablename__ = 'case_to_diff'

    id = Column(String(50), nullable=False, primary_key=True)


class DiffedCase(Base):
    __tablename__ = 'diffed_case'

    id = Column(String(50), nullable=False, primary_key=True)


class DocCount(Base):
    __tablename__ = 'doc_count'

    kind = Column(String(50), primary_key=True)
    value = Column(Integer, nullable=False)


class DocDiffs(Base):
    __tablename__ = 'doc_diffs'

    kind = Column(String(50), nullable=False, primary_key=True)
    doc_id = Column(String(50), nullable=False, primary_key=True)
    diffs = Column(Text(), nullable=False)

    def diff_to_dict(diff):
        data = {"type": diff.diff_type, "path": diff.path}
        if diff.old_value is not MISSING:
            data["old_value"] = diff.old_value
        if diff.new_value is not MISSING:
            data["new_value"] = diff.new_value
        return data

    def dict_to_diff(kind, doc_id, data, *, _make_diff=Diff):
        def json_or_none(data, key):
            return json.dumps(data[key]) if key in data else None
        path = data["path"]
        if len(path) == 2 and isinstance(path, dict):
            assert path.keys() == {"stock_id", "path"}, path
            assert path["stock_id"].startswith(doc_id + "/"), (doc_id, path)
            kind = "stock state"
            doc_id = path["stock_id"]
            path = path["path"]
        return _make_diff(
            kind=kind,
            doc_id=doc_id,
            diff_type=data["type"],
            path=json.dumps(path),
            old_value=json_or_none(data, "old_value"),
            new_value=json_or_none(data, "new_value"),
        )


class DocChanges(Base):
    __tablename__ = 'doc_changes'

    kind = Column(String(50), nullable=False, primary_key=True)
    doc_id = Column(String(50), nullable=False, primary_key=True)
    diffs = Column(Text(), nullable=False)

    def diff_to_dict(diff):
        data = DocDiffs.diff_to_dict(diff)
        data["reason"] = diff.reason
        return data

    def dict_to_diff(kind, doc_id, data):
        def change(**kw):
            for key in ["path", "old_value", "new_value"]:
                kw[key] = MISSING if kw[key] is None else json.loads(kw[key])
            return Change(reason=data["reason"], **kw)
        return DocDiffs.dict_to_diff(kind, doc_id, data, _make_diff=change)


@attr.s
class Change:
    kind = attr.ib()
    doc_id = attr.ib()
    reason = attr.ib()
    diff_type = attr.ib()
    path = attr.ib()
    old_value = attr.ib()
    new_value = attr.ib()

    @property
    def json_diff(self):
        return self

    def _replace(self, **data):
        cls = type(self)
        for att in attr.fields(cls):
            if att.name not in data:
                data[att.name] = getattr(self, att.name)
        return cls(**data)


class KeyValue(Base):
    __tablename__ = "keyvalue"

    key = Column(String(50), nullable=False, primary_key=True)
    value = Column(Text(), nullable=False)


class MissingDoc(Base):
    __tablename__ = 'missing_doc'

    kind = Column(String(50), nullable=False, primary_key=True)
    doc_id = Column(String(50), nullable=False, primary_key=True)


class NoActionCaseForm(Base):
    __tablename__ = "noactioncaseform"

    id = Column(String(50), nullable=False, primary_key=True)


class PatchedCase(Base):
    __tablename__ = 'patchedcase'

    id = Column(String(50), nullable=False, primary_key=True)


class ProblemForm(Base):
    __tablename__ = "problemform"

    id = Column(String(50), nullable=False, primary_key=True)


@attr.s
class Counts:
    total = attr.ib(default=0)
    diffs = attr.ib(default=0)
    missing = attr.ib(default=0)
    changes = attr.ib(default=0)


def iter_large(query, pk_attr, maxrq=1000):
    """Specialized windowed query generator using WHERE/LIMIT

    Iterate over a dataset that is too large to fetch at once. Results
    are ordered by `pk_attr`.

    Adapted from https://github.com/sqlalchemy/sqlalchemy/wiki/WindowedRangeQuery
    """
    first_id = None
    while True:
        qry = query
        if first_id is not None:
            qry = query.filter(pk_attr > first_id)
        rec = None
        for rec in qry.order_by(pk_attr).limit(maxrq):
            yield rec
        if rec is None:
            break
        first_id = getattr(rec, pk_attr.name)
