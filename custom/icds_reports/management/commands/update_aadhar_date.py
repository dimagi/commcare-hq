from __future__ import absolute_import, print_function

from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from django.db import connections

from corehq.apps.locations.models import SQLLocation
from corehq.sql_db.routers import db_for_read_write
from custom.icds_reports.models import ChildHealthMonthly


CHILD_TABLENAME = "config_report_icds-cas_static-child_health_cases_a46c129f"
PERSON_TABLENAME = "config_report_icds-cas_static-person_cases_v2_b4b5d57a"

UPDATE_QUERY = """
UPDATE "{child_tablename}" child SET
  aadhar_date = person.aadhar_date
FROM "{person_tablename}" person
WHERE child.mother_id = person.doc_id AND child.supervisor_id = %(sup_id)s AND person.supervisor_id = %(sup_id)s
      AND lower("substring"(person.state_id, '.{3}$'::text)) = %(state_id_last_3)s
      AND lower("substring"(child.state_id, '.{3}$'::text)) = %(state_id_last_3)s
""".format(child_tablename=CHILD_TABLENAME, person_tablename=PERSON_TABLENAME)


def get_cursor(model):
    db = db_for_read_write(model)
    return connections[db].cursor()


class Command(BaseCommand):
    def handle(self, *args, **options):
        supervisors = (
            SQLLocation.objects
            .filter(domain='icds-cas', location_type__name='supervisor')
        )
        count = 0
        num_ids = supervisors.count()

        for sup in supervisors:
            with get_cursor(ChildHealthMonthly) as cursor:
                cursor.execute(UPDATE_QUERY, {
                    "sup_id": sup.location_id,
                    "state_id_last_3": sup.get_ancestor_of_type('state').location_id[-3:]
                })
            count += 1

            if count % 100 == 0:
                print("{} / {}".format(count, num_ids))
