from __future__ import absolute_import
from __future__ import unicode_literals

import errno
import os
import os.path
from collections import namedtuple

from django.conf import settings

from sqlalchemy import func, Column, Integer, String

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


class DocCount(Base):
    __tablename__ = 'doc_count'

    kind = Column(String(50), primary_key=True)
    value = Column(Integer, nullable=False)


class MissingDoc(Base):
    __tablename__ = 'missing_doc'

    id = Column(Integer, primary_key=True)
    kind = Column(String(50), nullable=False)
    doc_id = Column(String(50), nullable=False)


Counts = namedtuple('Counts', 'total missing')
