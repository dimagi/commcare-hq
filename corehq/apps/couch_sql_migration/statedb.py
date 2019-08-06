from __future__ import absolute_import
from __future__ import unicode_literals

import errno
import json
import os
import os.path
from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime

import six
from django.conf import settings

from memoized import memoized
from sqlalchemy import func, Column, Index, Integer, String, Text

from corehq.apps.tzmigration.planning import Base, DiffDB, PlanningDiff as Diff


def init_state_db(domain):
    db_filepath = _get_state_db_filepath(domain)
    return StateDB.init(db_filepath)


def open_state_db(domain):
    db_filepath = _get_state_db_filepath(domain)
    return StateDB.open(db_filepath)


def delete_state_db(domain):
    db_filepath = _get_state_db_filepath(domain)
    try:
        os.remove(db_filepath)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def _get_state_db_filepath(domain):
    return os.path.join(settings.SHARED_DRIVE_CONF.tzmigration_planning_dir,
                        '{}-tzmigration.db'.format(domain))


class StateDB(DiffDB):

    @classmethod
    def init(cls, path):
        is_new_db = not os.path.exists(path)
        db = super(StateDB, cls).init(path)
        if is_new_db:
            db._set_kv("db_unique_id", datetime.utcnow().strftime("%Y%m%d-%H%M%S.%f"))
        return db

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.engine.dispose()
        if self._connection is not None:
            self._connection.close()

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

    def add_problem_form(self, form_id):
        with self.session() as session:
            session.add(ProblemForm(id=form_id))

    def iter_problem_forms(self):
        query = self.Session().query(ProblemForm.id)
        for form_id, in iter_large(query, ProblemForm.id):
            yield form_id

    def add_no_action_case_form(self, form_id):
        with self.session() as session:
            session.add(NoActionCaseForm(id=form_id))
        self.get_no_action_case_forms.reset_cache(self)

    @memoized
    def get_no_action_case_forms(self):
        """Get the set of form ids that touch cases without actions"""
        return {x for x, in self.Session().query(NoActionCaseForm.id)}

    def set_resume_state(self, key, value):
        resume_key = "resume-{}".format(key)
        self._upsert(KeyValue, KeyValue.key, resume_key, json.dumps(value))

    def pop_resume_state(self, key, default):
        resume_key = "resume-{}".format(key)
        with self.session() as session:
            kv = self._get_kv(resume_key, session)
            if kv is None:
                self._set_kv(resume_key, RESUME_NOT_ALLOWED, session)
                value = default
            elif kv.value == RESUME_NOT_ALLOWED:
                raise ResumeError("previous session did not save resume state")
            else:
                value = json.loads(kv.value)
                kv.value = RESUME_NOT_ALLOWED
        return value

    def _get_kv(self, key, session):
        return session.query(KeyValue).filter_by(key=key).scalar()

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

    def add_unexpected_diff(self, case_id):
        """Add case that has been updated by a form it does not reference"""
        with self.session() as session:
            sql = (
                "INSERT OR IGNORE INTO {table} (id) VALUES (:id)"
            ).format(table=UnexpectedCaseUpdate.__tablename__)
            session.execute(sql, {"id": case_id})

    def iter_unexpected_diffs(self):
        """Iterate over case ids with unexpected diffs

        An "unexpected diff" is a case that was unexpectedly updated by
        a form it did not know about. All such case ids having at least
        one diff record will be yielded by this generator.
        """
        unex_id = UnexpectedCaseUpdate.id
        with self.session() as session:
            diff_ids = session.query(Diff.doc_id)
            query = session.query(unex_id).filter(unex_id.in_(diff_ids))
            for case_id, in iter_large(query, unex_id):
                yield case_id

    def discard_case_diffs(self, case_ids):
        assert not isinstance(case_ids, six.text_type), repr(case_ids)
        with self.session() as session:
            (
                session.query(Diff)
                .filter(Diff.kind == "CommCareCase", Diff.doc_id.in_(case_ids))
                .delete(synchronize_session=False)
            )

    def increment_counter(self, kind, value):
        self._upsert(DocCount, DocCount.kind, kind, value, incr=True)

    def get_doc_counts(self):
        """Returns a dict of counts by kind

        Values are `Counts` objects having `total` and `missing`
        fields:

        - total: number of items counted with `increment_counter`.
        - missing: count of ids added with `add_missing_docs`.
        """
        with self.session() as session:
            totals = {dc.kind: dc.value for dc in session.query(DocCount)}
            missing = {row[0]: row[1] for row in session.query(
                MissingDoc.kind,
                func.count(MissingDoc.doc_id),
            ).group_by(MissingDoc.kind).all()}
        return {kind: Counts(
            total=totals.get(kind, 0),
            missing=missing.get(kind, 0),
        ) for kind in set(missing) | set(totals)}

    def has_doc_counts(self):
        return self.engine.dialect.has_table(self.engine, "doc_count")

    def get_missing_doc_ids(self, doc_type):
        return {
            missing.doc_id for missing in self.Session()
            .query(MissingDoc.doc_id)
            .filter(MissingDoc.kind == doc_type)
        }


class ResumeError(Exception):
    pass


RESUME_NOT_ALLOWED = "RESUME_NOT_ALLOWED"


class DocCount(Base):
    __tablename__ = 'doc_count'

    kind = Column(String(50), primary_key=True)
    value = Column(Integer, nullable=False)


class KeyValue(Base):
    __tablename__ = "keyvalue"

    key = Column(String(50), nullable=False, primary_key=True)
    value = Column(Text(), nullable=False)


class MissingDoc(Base):
    __tablename__ = 'missing_doc'

    id = Column(Integer, primary_key=True)
    kind = Column(String(50), nullable=False)
    doc_id = Column(String(50), nullable=False)


class NoActionCaseForm(Base):
    __tablename__ = "noactioncaseform"

    id = Column(String(50), nullable=False, primary_key=True)


class ProblemForm(Base):
    __tablename__ = "problemform"

    id = Column(String(50), nullable=False, primary_key=True)


class UnexpectedCaseUpdate(Base):
    __tablename__ = "unexpectedcaseupdate"

    id = Column(String(50), nullable=False, primary_key=True)


diff_doc_id_idx = Index("diff_doc_id_idx", Diff.doc_id)


Counts = namedtuple('Counts', 'total missing')


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
