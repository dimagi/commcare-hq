from __future__ import absolute_import, print_function
from __future__ import unicode_literals

import six
import logging

from gevent.pool import Pool
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import connections
from memoized import memoized
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID, get_icds_ucr_db_alias
from custom.icds_reports.models.aggregate import AwcLocation
from custom.icds_reports.const import AggregationLevels, DASHBOARD_DOMAIN, AGG_INFRASTRUCTURE_TABLE
from dimagi.utils.logging import notify_exception


Base = declarative_base()
logger = logging.getLogger('backfill_supervisor_id')


class Status(object):
    NOT_STARTED = 'not_started'
    IN_PROGRESS = 'in_progress'
    FINISHED = 'finished'
    FAILED = 'failed'


class BackfillScriptStub(Base):
    __tablename__ = "backfill_supervisor_id"
    id = Column(Integer, primary_key=True)

    state_id = Column(String)
    ucr_id = Column(String)
    raw_sql_script = Column(String)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    # should be one of 'not_started', 'in_progress', 'finished', 'failed'
    status = Column(String, default=Status.NOT_STARTED)

    def __repr__(self):
        return "<BackfillScriptStub(state_id='%s', ucr_id='%s', progress='%s')>" % (
            self.state_id, self.ucr_id, self.status
        )


def get_raw_sql(ucr_table, join_table, ucr_column, join_table_column, state_id):
    template = """
    UPDATE "{ucr_table}" ucr
    SET supervisor_id = loc.supervisor_id
    FROM "{join_table}" loc
    WHERE ucr.{ucr_column} = loc.{join_table_column} and ucr.{ucr_column} is NOT NULL
        and loc.state_id = '{state_id}' and ucr.supervisor_id is NULL
    """
    sql = template.format(
        ucr_table=ucr_table, join_table=join_table,
        ucr_column=ucr_column, join_table_column=join_table_column,
        state_id=state_id
    )
    return sql


def get_sql_scripts(state_id):
    # check all tables have non-empty awc_id
    tables_with_awc_id = [
        # some awc_id of this UCR are null
        _table_name('static-pregnant-tasks_cases'),
        # some forms are from deleted locations, so loc table doesn't have data on some rows
        _table_name('static-usage_forms'),
        _table_name('static-child_tasks_cases'),
        _table_name('static-ccs_record_cases_monthly_v2'),
        _table_name('static-child_cases_monthly_v2'),
        'child_health_monthly',
        'daily_attendance',
        AGG_INFRASTRUCTURE_TABLE,
    ]

    child_health_ucrs = [
        # child_health_cases_a46c129f loc table has some empty supervisor_id
        _table_name('dashboard_child_health_daily_feeding_forms'),
        _table_name('static-dashboard_growth_monitoring_forms'),
        _table_name('static-complementary_feeding_forms')
    ]

    child_health_case_id = [
        'icds_dashboard_comp_feed_form',
        'icds_dashboard_child_health_thr_forms',
        'icds_dashboard_growth_monitoring_forms',
        'icds_dashboard_child_health_postnatal_forms',
        'icds_dashboard_daily_feeding_forms',

    ]

    # some supervisor_id on loc table are null
    ccs_record_ucrs = [
        _table_name('static-dashboard_birth_preparedness_forms'),
        _table_name('static-dashboard_thr_forms'),
        _table_name('static-postnatal_care_forms'),
    ]

    # has column 'case_load_ccs_record0'
    # some supervisor_id on loc table are null
    unclear_ccs_record = [_table_name('static-dashboard_delivery_forms')]
    ccs_record_case_d = [
        'icds_dashboard_ccs_record_delivery_forms',
        'icds_dashboard_ccs_record_cf_forms',
        'icds_dashboard_ccs_record_postnatal_forms',
        'icds_dashboard_ccs_record_bp_forms',
        'icds_dashboard_ccs_record_thr_forms',
        'ccs_record_monthly',
    ]

    ucr_to_sql = [
        # ([ucr_table_list, (join_table_name, ucr_column, join_table_column)])
        (tables_with_awc_id, (_table_name('static-awc_location'), 'awc_id', 'doc_id')),
        (child_health_ucrs, (
            _table_name('static-child_health_cases'),
            'child_health_case_id',
            'doc_id')),
        (ccs_record_ucrs, (
            _table_name('static-ccs_record_cases'),
            'ccs_record_case_id',
            'doc_id')),
        (unclear_ccs_record, (
            _table_name('static-ccs_record_cases'),
            'case_load_ccs_record0',
            'doc_id')),
        (ccs_record_case_d, (
            _table_name('static-ccs_record_cases'),
            'case_id',
            'doc_id')),
        (child_health_case_id, (
            _table_name('static-child_health_cases'),
            'case_id',
            'doc_id'
        ))
    ]
    sql_scripts = {}
    for ucrs, (join_table, ucr_column, join_table_column) in ucr_to_sql:
        for table in ucrs:
            sql_scripts[table] = get_raw_sql(table, join_table, ucr_column, join_table_column, state_id)
    return sql_scripts


def _table_name(table_id):
    return get_table_name(DASHBOARD_DOMAIN, table_id)


@memoized
def get_state_ids():
    return AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE).values_list('state_id', flat=True)


class Command(BaseCommand):
    help = "Backfill dashboard UCRs with supervisor_id one by one for each UCR/state_id"

    def add_arguments(self, parser):
        # can pass special value 'all' to backfill/show-status for all
        parser.add_argument('--state_id',
            action='store', default='',
            help='Not valid with --resetup_scripts')
        parser.add_argument('--ucr_id',
            action='store', default='',
            help='Not valid with --resetup_scripts')

        parser.add_argument(
            '--show_status',
            action='store_true',
            dest='show_status',
            help='Show status of the backfilling and exit'
        )

        parser.add_argument(
            '--resetup_scripts',
            action='store_true',
            dest='force_resetup',
            help='Cleanup all progress and restart the scripts'
        )

        parser.add_argument(
            '--setup_only',
            action='store_true',
            dest='setup_only',
            help='Setup scripts but dont start running them'
        )

    def handle(self, *args, **options):
        state_id = options['state_id']
        ucr_ids = options['ucr_id'].split(',') if options['ucr_id'] else []
        if options['show_status']:
            return self.show_status(state_id, ucr_ids)
        elif options['force_resetup']:
            assert not state_id, "state_id is not valid option with resetup_scripts"
            assert not ucr_ids, "ucr_id is not valid option with resetup_scripts"
            self.show_status(None, None)
            self.boostrap_sql_scripts(force=True)
            self.start_scripts(None, None)
        elif options['setup_only']:
            self.boostrap_sql_scripts(force=False)
        else:
            self.boostrap_sql_scripts(force=False)
            self.start_scripts(state_id, ucr_ids)

    def start_scripts(self, state_id, ucr_ids):
        state_ids = [state_id] if state_id else get_state_ids()
        if not ucr_ids:
            ucr_ids = get_sql_scripts(state_id).keys()
        pool = Pool(5)
        for ucr_id in ucr_ids:
            for state_id in state_ids:
                rows = self.get_session().query(BackfillScriptStub).filter_by(state_id=state_id, ucr_id=ucr_id).all()
                assert len(rows) == 1, ("There should be just one row", ucr_id, state_id)
                if rows[0].status in [Status.NOT_STARTED, Status.FAILED]:
                    pool.spawn(self.run_sql_script, state_id, ucr_id)
                else:
                    logger.info("Backfilling already done for {} for state:{}, skipping.".format(ucr_id, state_id))
        pool.join()

    @memoized
    def get_session(self):
        return connection_manager.get_session_helper(ICDS_UCR_ENGINE_ID).Session

    def get_engine(self):
        return connection_manager.get_engine(ICDS_UCR_ENGINE_ID)

    def show_status(self, state_id, ucr_ids):
        engine = self.get_engine()
        if not engine.dialect.has_table(engine, BackfillScriptStub.__table__.name):
            return
        query = self.get_session().query(BackfillScriptStub)
        if state_id:
            query = query.filter_by(state_id=state_id)
        if ucr_ids:
            query = query.filter_by(ucr_id__in=ucr_ids)
        for row in query.order_by('started_at').all():
            print(row.ucr_id, row.state_id, row.started_at, row.ended_at, row.status)
        return

    def boostrap_sql_scripts(self, force=False):
        # query if there are already scripts, raise error if so
        engine = self.get_engine()
        session = self.get_session()
        previous_table_exists = engine.dialect.has_table(engine, BackfillScriptStub.__table__.name)
        if force and previous_table_exists:
            session.close()
            BackfillScriptStub.__table__.drop(engine)
            Base.metadata.create_all(engine)
        elif previous_table_exists:
            logging.info("Scripts are already setup. Setting up missing ones only, use --resetup_scripts to force resetup")
        else:
            Base.metadata.create_all(engine)
        existing = [
            (stub.state_id, stub.ucr_id)
            for stub in session.query(BackfillScriptStub).all()
        ]
        rows = []
        for state_id in get_state_ids():
            scripts_by_ucr = get_sql_scripts(state_id)
            for ucr_id, script in six.iteritems(scripts_by_ucr):
                if (state_id, ucr_id) not in existing:
                    logger.info("Setting up stub for {} {}".format(state_id, ucr_id))
                    rows.append(BackfillScriptStub(state_id=state_id, ucr_id=ucr_id, raw_sql_script=script))
        session.add_all(rows)
        session.commit()
        logger.info("Status stubs have been setup.")

    def run_sql_script(self, state_id, ucr_id):
        # query the row, raise error if already started/updated, otherwise proceed
        logger.info("Starting the backfill script for state_id:{}, {}".format(state_id, ucr_id))
        session = self.get_session()
        rows = session.query(BackfillScriptStub).filter_by(state_id=state_id, ucr_id=ucr_id).all()
        assert len(rows) == 1, "There were either no scripts generated or multiple scripts exist"
        backfill_stub = rows[0]
        backfill_stub.started_at = datetime.now()
        backfill_stub.status = Status.IN_PROGRESS
        session.commit()
        try:
            db_alias = get_icds_ucr_db_alias()
            with connections[db_alias].cursor() as cursor:
                cursor.execute(backfill_stub.raw_sql_script)
        except Exception:
            notify_exception(None, "Backfilling UCRs with supervisor_id failed for {}, {}".format(
                state_id, ucr_id))
            backfill_stub.status = Status.FAILED
        else:
            logger.info("Backfill script for state_id:{}, {} is finished".format(state_id, ucr_id))
            backfill_stub.status = Status.FINISHED
        finally:
            backfill_stub.ended_at = datetime.now()
            session.commit()
