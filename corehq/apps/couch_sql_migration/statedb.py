from __future__ import absolute_import
from __future__ import unicode_literals

import errno
import json
import os
import os.path
from collections import namedtuple
from datetime import datetime

from django.conf import settings

from memoized import memoized
from sqlalchemy import func, Column, Integer, String, Text

from corehq.apps.tzmigration.planning import Base, DiffDB


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
            db.save_resume_state([])
        return db

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.engine.dispose()
        if self._connection is not None:
            self._connection.close()

    @property
    @memoized
    def unique_id(self):
        return self._get_kv("db_unique_id").value

    def add_problem_form(self, form_id):
        session = self.Session()
        session.add(ProblemForm(id=form_id))
        session.commit()

    def iter_problem_forms(self):
        query = self.Session().query(ProblemForm.id)
        for form_id, in iter_large(query, ProblemForm.id):
            yield form_id

    def add_no_action_case_form(self, form_id):
        session = self.Session()
        session.add(NoActionCaseForm(id=form_id))
        session.commit()
        self.get_no_action_case_forms.reset_cache(self)

    @memoized
    def get_no_action_case_forms(self):
        """Get the set of form ids that touch cases without actions"""
        return {x for x, in self.Session().query(NoActionCaseForm.id)}

    def save_resume_state(self, state):
        self._set_kv("resume_state", json.dumps(state))

    def pop_saved_resume_state(self):
        value = self._pop_kv("resume_state")
        if value is None:
            raise ResumeError(
                "Cannot resume because previous session did not exit cleanly.")
        return json.loads(value.value)

    def _get_kv(self, key, session=None):
        if session is None:
            session = self.Session()
        return session.query(KeyValue).filter_by(key=key).scalar()

    def _pop_kv(self, key):
        session = self.Session()
        kv = self._get_kv(key, session)
        if kv is not None:
            session.delete(kv)
            session.commit()
        return kv

    def _set_kv(self, key, value):
        session = self.Session()
        session.add(KeyValue(key=key, value=value))
        session.commit()

    def add_missing_docs(self, kind, doc_ids):
        session = self.Session()
        session.bulk_save_objects([
            MissingDoc(kind=kind, doc_id=doc_id)
            for doc_id in doc_ids
        ])
        session.commit()

    def increment_counter(self, kind, value):
        session = self.Session()
        updated = (
            session.query(DocCount)
            .filter_by(kind=kind)
            .update(
                {DocCount.value: DocCount.value + value},
                synchronize_session=False,
            )
        )
        if not updated:
            session.add(DocCount(kind=kind, value=value))
        else:
            assert updated == 1, (kind, updated)
        session.commit()

    def get_doc_counts(self):
        """Returns a dict of counts by kind

        Values are `Counts` objects having `total` and `missing`
        fields:

        - total: number of items counted with `increment_counter`.
        - missing: count of ids added with `add_missing_docs`.
        """
        session = self.Session()
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
