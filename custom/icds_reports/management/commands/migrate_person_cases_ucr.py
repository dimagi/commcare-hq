from __future__ import absolute_import, print_function

from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from django.db import connections
from corehq.apps.locations.models import SQLLocation
from corehq.sql_db.routers import db_for_read_write
from corehq.util.log import with_progress_bar
from custom.icds_reports.models import ChildHealthMonthly


FROM_TABLENAME = "config_report_icds-cas_static-person_cases_v2_b4b5d57a"
TO_TABLENAME = "config_report_icds-cas_static-person_cases_v3_2ae0879a"


def get_cursor(model):
    db = db_for_read_write(model)
    return connections[db].cursor()


class Command(BaseCommand):
    def handle(self, *args, **options):
        columns = (
            # person_v3, calculation from person_v2
            ("doc_id", ),
            ("inserted_at", ),
            ("awc_id", ),
            ("supervisor_id", ),
            ("block_id", ),
            ("district_id", ),
            ("state_id", ),
            ("opened_on", ),
            ("closed_on", ),
            ("name", ),
            ("sex", ),
            ("dob", ),
            ("age_at_reg", ),
            ("date_death", ),
            ("resident", "CASE WHEN resident = 'yes' THEN 1 WHEN resident = 'no' THEN 0 ELSE NULL END"),
            ("age_at_death_yrs", ),
            ("female_death_type", ),
            ("referral_health_problem", ),
            ("last_referral_date", ),
            ("referral_reached_date", ),
            ("hh_caste",
                "CASE WHEN \"F_sc_count\" = 1 OR \"M_sc_count\" = 1 THEN 'sc'"
                "     WHEN \"F_st_count\" = 1 OR \"M_st_count\" = 1 THEN 'st'"
                "     ELSE NULL END"),
            ("hh_minority", "CASE WHEN \"F_minority_count\" = 1 OR \"M_minority_count\" = 1 THEN 1 ELSE NULL END"),
            ("disabled", "CASE WHEN \"F_disabled_count\" = 1 OR \"M_disabled_count\" = 1 THEN 1 ELSE NULL END"),
            ("disability_type", "CONCAT_WS(' ', "
                "CASE WHEN disability_type_1 = 1 THEN 1 ELSE NULL END, "
                "CASE WHEN disability_type_2 = 1 THEN 2 ELSE NULL END, "
                "CASE WHEN disability_type_3 = 1 THEN 3 ELSE NULL END, "
                "CASE WHEN disability_type_4 = 1 THEN 4 ELSE NULL END, "
                "CASE WHEN disability_type_5 = 1 THEN 5 ELSE NULL END, "
                "CASE WHEN disability_type_6 = 1 THEN 6 ELSE NULL END "
                ")"),
            ("registered_status",
                "CASE WHEN seeking_services = 1 THEN NULL"
                "     WHEN seeking_services = 0 AND not_migrated = 1 THEN 0"
                "     ELSE NULL END"),
            ("migration_status", "CASE WHEN not_migrated = 0 THEN 1 ELSE NULL END"),
            ("aadhar_date", ),
            ("age_marriage", ),
            ("is_pregnant",
                "CASE WHEN pregnant_resident_count = 1 OR pregnant_migrant_count = 1 THEN 1 ELSE NULL END"),
            ("marital_status", ),
            # may need to remove if https://github.com/dimagi/commcare-hq/pull/22247 hasn't been merged
            ("phone_number", ),
        )
        query_columns = [
            "{} AS {}".format(col[0] if len(col) == 1 else col[1], col[0])
            for col in columns
        ]

        blocks = SQLLocation.objects.filter(domain='icds-cas', location_type__name='block')
        for block in with_progress_bar(blocks, blocks.count()):
            block_id = block.location_id
            state = block.get_ancestor_of_type('state')
            state_id = state.location_id

            with get_cursor(ChildHealthMonthly) as cursor:
                query_args = {'state_id': state_id, 'block_id': block_id, 'state_id_last_3': state_id[-3:]}
                cursor.execute(
                    "INSERT INTO \"{to_tablename}\" "
                    "SELECT {columns} "
                    "FROM \"{from_tablename}\" "
                    "WHERE state_id = %(state_id)s "
                    "AND lower(substring(state_id, '.{{3}}$'::text)) = %(state_id_last_3)s "
                    "AND block_id = %(block_id)s".format(
                        to_tablename=TO_TABLENAME,
                        from_tablename=FROM_TABLENAME,
                        columns=", \n".join(query_columns)
                    ), query_args)
