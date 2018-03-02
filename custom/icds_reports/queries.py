from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports import const
import sqlalchemy
from sqlalchemy.sql import select, func, case
from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID
from corehq.apps.userreports.util import get_table_name
from datetime import datetime

DATA_NOT_ENTERED = "Data Not Entered"


@quickcache(['domain'], timeout=5 * 60)
def get_test_state_locations_id(domain):
    return [
        sql_location.location_id
        for sql_location in SQLLocation.by_domain(domain).filter(location_type__code=const.LocationTypes.STATE)
        if sql_location.metadata.get('is_test_location', 'real') == 'test'
    ]


@quickcache(['domain'], timeout=5 * 60)
def get_test_district_locations_id(domain):
    return [
        sql_location.location_id
        for sql_location in SQLLocation.by_domain(domain).filter(location_type__code=const.LocationTypes.DISTRICT)
        if sql_location.metadata.get('is_test_location', 'real') == 'test'
    ]


def get_beneficiary_list(domain, awc_id, month, start, length, sort):
    engine = connection_manager.get_engine(ICDS_UCR_ENGINE_ID)
    metadata = sqlalchemy.MetaData(bind=engine)
    metadata.reflect(bind=engine, extend_existing=True)
    ucr_table = metadata.tables[get_table_name(domain, 'static-child_health_cases')]
    chm_table = metadata.tables['child_health_monthly']

    def status_helper(column, second_part, normal_value, sort_value=False):
        return case(
            [
                (
                    column.in_(('severely_underweight', 'severe')),
                    'Severely ' + second_part if not sort_value else 1
                ),
                (
                    column.in_(('moderately_underweight', 'moderate')),
                    'Moderately ' + second_part if not sort_value else 2
                ),
                (
                    column.in_(('normal',)),
                    normal_value if not sort_value else 3
                )
            ],
            else_=DATA_NOT_ENTERED if not sort_value else 4
        )

    count_query = select(
        [
            func.count(ucr_table.c.case_id)
        ]
    ).select_from(
        ucr_table.join(
            chm_table,
            chm_table.c.case_id == ucr_table.c.doc_id
        )
    ).where(
        chm_table.c.month == datetime(*month)
    ).where(
        chm_table.c.awc_id == awc_id
    ).where(
        chm_table.c.open_in_month == 1
    ).where(
        chm_table.c.valid_in_month == 1
    ).where(
        chm_table.c.age_in_months <= 60
    )

    select_query = select(
        [
            ucr_table.c.case_id.label('case_id'),
            ucr_table.c.name.label('person_name'),
            ucr_table.c.dob.label('dob'),
            chm_table.c.age_in_months.label('age_in_month'),
            status_helper(
                chm_table.c.current_month_nutrition_status,
                'underweight',
                'Normal weight for age'
            ).label('nutrition_status'),
            status_helper(
                chm_table.c.current_month_nutrition_status,
                'underweight',
                'Normal weight for age',
                True
            ).label('current_month_nutrition_status'),
            chm_table.c.recorded_weight,
            chm_table.c.recorded_height,
            status_helper(
                chm_table.c.current_month_stunting,
                'stunted',
                'Normal height for age'
            ),
            status_helper(
                chm_table.c.current_month_stunting,
                'underweight',
                'Normal weight for age',
                True
            ).label('current_month_stunting'),
            status_helper(
                chm_table.c.current_month_wasting,
                'wasted',
                'Normal weight for height'
            ),
            status_helper(
                chm_table.c.current_month_wasting,
                'underweight',
                'Normal weight for age',
                True
            ).label('current_month_wasting'),
            chm_table.c.pse_days_attended.label('pse_days_attended'),
            case(
                [
                    (
                        chm_table.c.fully_immunized_on_time > chm_table.c.fully_immunized_late,
                        chm_table.c.fully_immunized_on_time
                    )
                ],
                else_=chm_table.c.fully_immunized_late
            ).label('fully_immunized')
        ]
    ).select_from(
        ucr_table.join(
            chm_table,
            chm_table.c.case_id == ucr_table.c.doc_id
        )
    ).where(
        chm_table.c.month == datetime(*month)
    ).where(
        chm_table.c.awc_id == awc_id
    ).where(
        chm_table.c.open_in_month == 1
    ).where(
        chm_table.c.valid_in_month == 1
    ).where(
        chm_table.c.age_in_months <= 60
    ).order_by(sort)

    total_count = count_query.execute().fetchone()
    data = select_query.limit(length).offset((start / length) + 1).execute()
    return data, total_count[0]


def get_growth_monitoring_details(domain, case_id):
    engine = connection_manager.get_engine(ICDS_UCR_ENGINE_ID)
    metadata = sqlalchemy.MetaData(bind=engine)
    metadata.reflect(bind=engine, extend_existing=True)
    ucr_table = metadata.tables[get_table_name(domain, 'static-child_health_cases')]
    chm_table = metadata.tables['child_health_monthly']

    select_query = select(
        [
            ucr_table.c.case_id,
            ucr_table.c.name,
            ucr_table.c.mother_name,
            ucr_table.c.dob,
            ucr_table.c.sex,
            chm_table.c.age_in_months,
            chm_table.c.recorded_weight,
            chm_table.c.recorded_height,
        ]
    ).select_from(
        ucr_table.join(
            chm_table,
            chm_table.c.case_id == ucr_table.c.doc_id
        )
    ).where(
        chm_table.c.case_id == case_id
    ).order_by('month asc')

    return select_query.execute()
