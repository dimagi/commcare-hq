import csv

from django.core.management.base import BaseCommand
from django.db import connections
from datetime import datetime
from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.utils.connections import get_icds_ucr_citus_db_alias

"""
The way query variables are structured is, they will have a fixed starting and a fixed end.
And the middle condition is variable based on the type of beneficary we are targetting.
"""

COMMON_QUERY_START = """SELECT
person_cases.state_id,
person_cases.district_id,
COUNT(*) "count",
SUM(
    CASE
        WHEN person_cases.phone_number SIMILAR TO '[6789][0-9]{9}' THEN 1 ELSE 0
    END) "valid_phone_count",
SUM(
    CASE WHEN (person_cases.phone_number != ''  AND person_cases.phone_number IS NOT NULL)  AND phone_number NOT SIMILAR to '[6789][0-9]{9}' THEN 1 ELSE 0
    END) "invalid_phone_count",
SUM(
    CASE
        WHEN (person_cases.phone_number = '') IS NOT FALSE  THEN 1 ELSE 0
    END) "phone_not_available"
 """

COMMON_QUERY_END = """ and person_cases.migration_status=0 and person_cases.doc_id is not null and person_cases.closed_on is null and person_cases.registered_status=1
group by
person_cases.state_id, person_cases.district_id"""

CONDITION_PREGNANT_WOMAN = """ FROM "ucr_icds-cas_static-person_cases_v3_2ae0879a" person_cases
where person_cases.is_pregnant=1 """

CONDITION_LACTATING_MOTHER = """ FROM "ucr_icds-cas_static-ccs_record_cases_cedcca39" ccs_record
LEFT OUTER JOIN "ucr_icds-cas_static-person_cases_v3_2ae0879a" person_cases
ON
    ccs_record.person_case_id = person_cases.doc_id
    AND
    ccs_record.supervisor_id = person_cases.supervisor_id
where ccs_record.add is not null AND now() - ccs_record.add  < '182 days' ::interval """

CONDITION_CHILDREN = """ FROM "ucr_icds-cas_static-child_health_cases_a46c129f" child_health
LEFT OUTER JOIN "ucr_icds-cas_static-person_cases_v3_2ae0879a" person_cases
ON
    child_health.mother_id = person_cases.doc_id
    AND
    child_health.state_id = person_cases.state_id
    AND
    child_health.supervisor_id = person_cases.supervisor_id
where child_health.dob is NOT null AND now() - child_health.dob <= '2191.5 days' ::interval """

CONDITION_WOMEN_LESS_THAN_45 = """ FROM "ucr_icds-cas_static-person_cases_v3_2ae0879a" person_cases
where  person_cases.sex = 'F' AND now() - person_cases.dob >= '4017.75 days' ::interval and now() - person_cases.dob <= '17897.25 days' :: interval """

CONDITION_ALL_WOMEN = """ FROM "ucr_icds-cas_static-person_cases_v3_2ae0879a" person_cases
where  person_cases.sex = 'F' AND now() - person_cases.dob >= '4017.75 days' ::interval """

BENEFICIARY_TYPES = ["PW", "LM", "Children", "Women Less than 45 yrs", "All Women"]

CSV_FILENAME = "phone_number_info_grouped_by_districts_{datetime}.csv".format(
    datetime=datetime.utcnow()
)

STATE_CODE=170
DISTRICT_CODE=171

class Command(BaseCommand):
    def prepare_query(self, condition):
        return COMMON_QUERY_START + condition + COMMON_QUERY_END

    def get_loc_name(self, loc):
        return self.location_map.get(loc, "Unknown Location")
        
    def prepare_location_map(self):
        all_locations = SQLLocation.objects.filter(
            domain='icds-cas',
            location_type__in=[STATE_CODE, DISTRICT_CODE]
        )
        self.location_map={}
        for location in all_locations:
            if location.metadata.get('is_test_location') != 'test':
                self.location_map[location.location_id] = location.name
        return self.location_map

    def get_variable_headers(self):
        return ['Count', 'Valid Phone Numbers', 'Invalid Phone Numbers', 'No Phone Numbers']

    def get_fixed_header_names(self):
        return ['State', 'District']

    def get_location_key(self, state_id, district_id):
        return state_id + '_' + district_id

    def get_placeholders_for_empty_rows(self, count):
        placeholders = ()
        for i in range(count):
            placeholders += 0,
        return placeholders

    def append_data_to_result(self, row, count):
        key = self.get_location_key(row[0], row[1])
        state = self.get_loc_name(row[0])
        district = self.get_loc_name(row[1])
        expected_entries = (count * 4) + 2
        if not self.result_map.get(key):
            self.result_map[key] = (state, district)
        present_entries = len(self.result_map[key])
        self.result_map[key] += (0,) * (expected_entries -present_entries)
        present_entries = len(self.result_map[key])
        self.result_map[key] += row[2:]

    def get_all_headers(self):
        fixed_headers = self.get_fixed_header_names()
        other_headers = []
        for b_type in BENEFICIARY_TYPES:
            for header in self.get_variable_headers():
                other_headers.append(b_type + ' ' + header)
        return fixed_headers + other_headers

    def beneficiary_query_conditions(self):
        return [
            CONDITION_PREGNANT_WOMAN,
            CONDITION_LACTATING_MOTHER,
            CONDITION_CHILDREN,
            CONDITION_WOMEN_LESS_THAN_45,
            CONDITION_ALL_WOMEN
        ]

    def create_csv_file(self):
        with open(CSV_FILENAME, 'w') as output:
            writer = csv.writer(output)
            writer.writerow(self.get_all_headers())
            for _, row in self.result_map.items():
                if row[0] != 'Unknown Location' and row[1] != 'Unknown Location':
                    writer.writerow(row)

    def handle(self, *args, **options):
        self.prepare_location_map()
        self.result_map = {}
        query_condtions = self.beneficiary_query_conditions()
        db_alias = get_icds_ucr_citus_db_alias()
        with connections[db_alias].cursor() as cursor:
            for count, condition in enumerate(query_condtions):
                query = self.prepare_query(condition)
                cursor.execute(query)
                output = cursor.fetchall()
                for row in output:
                    try:
                        self.append_data_to_result(row, count)
                    except Exception as e:
                        print("Error processing row", row)
                        print("Raised Exception", e)
        self.create_csv_file()
