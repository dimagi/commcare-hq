from __future__ import absolute_import
from __future__ import unicode_literals
import json
import sqlite3
from sqlite3 import dbapi2 as sqlite

from sqlalchemy import create_engine, Column, Integer, ForeignKey, String, \
    UnicodeText, Text
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from corehq.apps.hqwebapp.encoders import LazyEncoder

Base = declarative_base()


class PlanningForm(Base):
    __tablename__ = 'form'

    id = Column(Integer, primary_key=True)
    uuid = Column(String(50), nullable=False, unique=True)
    form_json = Column(UnicodeText, nullable=False)


class PlanningCase(Base):
    __tablename__ = 'case'

    id = Column(Integer, primary_key=True)
    uuid = Column(String(50), nullable=False, unique=True)
    case_json = Column(UnicodeText, nullable=True)
    doc_type = Column(String(50), nullable=True)


class PlanningCaseAction(Base):
    __tablename__ = 'case_action'

    id = Column(Integer, primary_key=True)
    form = Column(Integer, ForeignKey('form.id'), nullable=False)
    case = Column(Integer, ForeignKey('case.id'), nullable=False)
    action_json = Column(UnicodeText, nullable=False)


class PlanningDiff(Base):
    __tablename__ = 'diff'

    id = Column(Integer, primary_key=True)
    kind = Column(String(50), nullable=False)
    doc_id = Column(String(50), nullable=False)
    diff_type = Column(String(50), nullable=False)
    path = Column(Text(), nullable=False)
    old_value = Column(UnicodeText, nullable=True)
    new_value = Column(UnicodeText, nullable=True)

    @property
    def json_diff(self):
        from corehq.apps.tzmigration.timezonemigration import FormJsonDiff, MISSING

        def json_loads_or_missing(val):
            if val is None:
                return MISSING
            else:
                return json.loads(val)

        return FormJsonDiff(
            self.diff_type, json.loads(self.path),
            json_loads_or_missing(self.old_value),
            json_loads_or_missing(self.new_value)
        )


class PlanningStockReportHelper(Base):
    __tablename__ = 'stock_report_helper'

    id = Column(Integer, primary_key=True)
    form = Column(Integer, ForeignKey('form.id'), nullable=False)
    stock_report_helper_json = Column(UnicodeText, nullable=False)


class BaseDB(object):

    def __init__(self, db_filepath):
        self.db_filepath = db_filepath
        self._connection = None
        self.engine = create_engine(
            'sqlite+pysqlite:///{}'.format(db_filepath), module=sqlite)
        self.Session = sessionmaker(bind=self.engine)

    @classmethod
    def init(cls, db_filepath):
        self = cls(db_filepath)
        Base.metadata.create_all(self.engine)
        return self

    @classmethod
    def open(cls, db_filepath):
        return cls(db_filepath)

    @property
    def connection(self):
        if not self._connection:
            self._connection = sqlite3.connect(self.db_filepath)
        return self._connection


class DiffDB(BaseDB):
    def add_diffs(self, kind, doc_id, doc_diffs):
        from corehq.apps.tzmigration.timezonemigration import MISSING
        session = self.Session()

        def json_dumps_or_none(val):
            if val is MISSING:
                return None
            else:
                return json.dumps(val, cls=LazyEncoder)

        for d in doc_diffs:
            session.add(PlanningDiff(
                kind=kind,
                doc_id=doc_id, diff_type=d.diff_type, path=json.dumps(d.path),
                old_value=json_dumps_or_none(d.old_value),
                new_value=json_dumps_or_none(d.new_value)))
        session.commit()

    def get_diffs(self):
        session = self.Session()
        return session.query(PlanningDiff).all()

    def get_diff_stats(self):
        """
        :return: {
            doc_type: (diff_count, doc_id_count),
            ...
        }
        """
        session = self.Session()
        results = session.query(
            PlanningDiff.kind,
            func.count(PlanningDiff.id),
            func.count(distinct(PlanningDiff.doc_id))
        ).group_by(PlanningDiff.kind).all()
        return {
            res[0]: (res[1], res[2])
            for res in results
        }


class PlanningDB(DiffDB):
    def add_form(self, form_id, form_json):
        session = self.Session()
        session.add(PlanningForm(uuid=form_id, form_json=json.dumps(form_json)))
        session.commit()

    def ensure_case(self, case_id):
        session = self.Session()
        try:
            (session.query(PlanningCase)
             .filter(PlanningCase.uuid == case_id).one())
        except NoResultFound:
            session.add(PlanningCase(uuid=case_id))
            session.commit()

    def add_case_actions(self, case_id, case_actions):
        session = self.Session()
        for xform_id, case_action in case_actions:
            session.add(PlanningCaseAction(
                form=xform_id, case=case_id,
                action_json=json.dumps(case_action)))
        session.commit()

    def add_stock_report_helpers(self, stock_report_helpers):
        session = self.Session()
        for stock_report_helper in stock_report_helpers:
            session.add(
                PlanningStockReportHelper(
                    form=stock_report_helper.form_id,
                    stock_report_helper_json=json.dumps(stock_report_helper)))
        session.commit()

    def get_all_form_ids(self):
        session = self.Session()

        form_ids = {
            uuid for (uuid,) in
            session.query(PlanningForm).with_entities(PlanningForm.uuid).all()
        }
        return form_ids

    def get_all_case_ids(self, valid_only=True):
        """Exclude CommCareCare-Deleted"""
        session = self.Session()
        query = session.query(PlanningCase).with_entities(PlanningCase.uuid)
        if valid_only:
            query = query.filter(PlanningCase.doc_type == 'CommCareCase')
        case_ids = {uuid for (uuid,) in query.all()}
        return case_ids

    def update_case_json(self, case_id, case_json):
        session = self.Session()
        (session.query(PlanningCase).filter(PlanningCase.uuid == case_id)
         .update({'case_json': json.dumps(case_json)}))
        session.commit()

    def update_case_doc_type(self, case_id, doc_type):
        session = self.Session()
        (session.query(PlanningCase).filter(PlanningCase.uuid == case_id)
         .update({'doc_type': doc_type}))
        session.commit()

    def get_actions_by_case(self, case_id):
        session = self.Session()
        result = (
            session.query(PlanningCaseAction)
            .filter(PlanningCaseAction.case == case_id)
            # this should keep them in form insert order
            .order_by(PlanningCaseAction.id)
            .with_entities(PlanningCaseAction.action_json))
        return [json.loads(action_json) for action_json, in result]

    def get_forms(self):
        session = self.Session()
        return (json.loads(form_json) for form_json, in
                session.query(PlanningForm).order_by(PlanningForm.id)
                .with_entities(PlanningForm.form_json).all())

    def get_cases(self):
        session = self.Session()
        return (json.loads(case_json) for case_json, in
                session.query(PlanningCase).order_by(PlanningCase.id)
                .with_entities(PlanningCase.case_json).all())
