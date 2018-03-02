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


engine = connection_manager.get_engine(ICDS_UCR_ENGINE_ID)
metadata = sqlalchemy.MetaData(bind=engine)
metadata.reflect(bind=engine, extend_existing=True)


def get_beneficiary_list(awc_id, month, start, length, sort):

    ucr_table = metadata.tables[get_table_name('icds-dashboard-qa', 'static-child_health_cases')]
    chm_table = metadata.tables['child_health_monthly']

    def status_helper(second_part, normal_value, sort_value=False):
        return case(
            [
                (
                    chm_table.c.current_month_nutrition_status.in_(('severely_underweight', 'severe')),
                    'Severely ' + second_part if not sort_value else 1
                ),
                (
                    chm_table.c.current_month_nutrition_status.in_(('moderately_underweight', 'moderate')),
                    'Moderately ' + second_part if not sort_value else 2
                ),
                (
                    chm_table.c.current_month_nutrition_status.in_(('normal')),
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
            chm_table.c.age_in_months,
            status_helper('underweight', 'Normal weight for age').label('nutrition_status'),
            status_helper('underweight', 'Normal weight for age', True).label('nutrition_status_sort'),
            chm_table.c.recorded_weight,
            chm_table.c.recorded_height,
            status_helper('stunted', 'Normal height for age').label('stunting_status'),
            status_helper('underweight', 'Normal weight for age', True).label('stunting_status_sort'),
            status_helper('wasted', 'Normal weight for height').label('wasting_status'),
            status_helper('underweight', 'Normal weight for age', True).label('wasting_status_sort'),
            chm_table.c.pse_days_attended,
            case(
                [
                    (
                        chm_table.c.fully_immunized_on_time > chm_table.c.fully_immunized_late,
                        chm_table.c.fully_immunized_on_time
                    )
                ],
                else_=chm_table.c.fully_immunized_late
            )
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


def get_beneficiary_list_old(awc_id, month, start, length, order):
    from custom.icds_reports.models import ChildHealthMonthlyView
    from custom.icds_reports.utils import get_status
    data = ChildHealthMonthlyView.objects.filter(
        month=datetime(*month),
        awc_id=awc_id,
        open_in_month=1,
        valid_in_month=1,
        age_in_months__lte=60
    )

    data_count = data.count()
    if 'current_month_nutrition_status' in order:
        sort_order = {
            'Severely underweight': 1,
            'Moderately underweight': 2,
            'Normal weight for age': 3,
            'Data Not Entered': 4
        }
        reverse = '-' in order
        data = sorted(
            data,
            key=lambda val: (sort_order[
                                 get_status(
                                     val.current_month_nutrition_status,
                                     'underweight',
                                     'Normal weight for age'
                                 )['value']
                             ]),
            reverse=reverse
        )
    else:
        data = data.order_by('-month', order)

    return data[start:(start + length)], data_count
