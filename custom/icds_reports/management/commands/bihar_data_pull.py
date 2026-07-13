from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
import csv

from django.core.management.base import BaseCommand

from django.db import connections, transaction
from datetime import date
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


headers = [
    'District',
    'Block',
    'Sector',
    'Sector Code',
    'AWC',
    'AWC Code (11 Digit)',
    'Name of Beneficiary',
    'Age',
    'Male/Female',
    'Pregnant or not (If applicable)',
    'Phone_Number',
    'adhar number',
    'Has Bank Account?',
    'Bank IFSC Code',
    'Bank Account Number',
    'Bank Name',
    'husband Name'
]
data_rows = [headers]


def _run_custom_sql_script(command, day=None):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return

    cursor = connections[db_alias].cursor()
    cursor.execute(command, [day])

    return cursor.fetchall()


def ccs_record_cases():
    query = """
        Select
            district_name,
            block_name,
            supervisor_name,
            supervisor_site_code,
            awc_name,
            awc_site_code,
            case_id,
            person_case_id,
            person_name,
            husband_name,
            EXTRACT(year FROM age(CURRENT_DATE,dob::date))
            mobile_number
        from ccs_record_monthly
        INNER join awc_location ON
                    ccs_record_monthly.awc_id = awc_location.doc_id AND
                    ccs_record_monthly.supervisor_id = awc_location.supervisor_id AND
                    awc_location.aggregation_level=5 AND
                    awc_location.state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
        WHERE ccs_record_monthly.migration_status is distinct from 1 AND ccs_record_monthly.month='2020-04-01'
        """
    return _run_custom_sql_script(query)


def get_age_from_dob(dob):
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class Command(BaseCommand):
    help = "Run Bihar Data Pull"

    def handle(self, **options):
        case_accessor = CaseAccessors('icds-cas')

        ccs_cases = ccs_record_cases()

        ccs_case_ids = [case[6] for case in ccs_cases]
        person_case_ids = [case[7] for case in ccs_cases]

        # this is slower but 100000 times faster than scraping case by case
        ccs_cases = case_accessor.get_cases(ccs_case_ids)
        person_cases = case_accessor.get_cases(person_case_ids)

        person_cases_dict = {case.get_case_property('case_id'): case for case in person_cases}
        ccs_cases_dict = {case.get_case_property('case_id'): case for case in ccs_cases}

        data_rows = [headers]

        for case in ccs_cases:
            case_obj = ccs_cases_dict[case[6]]
            person_case_obj = person_cases_dict[case[7]]
            row = [
                case[0],
                case[1],
                case[2],
                case[3],
                case[4],
                case[5],
                case[8],
                case[10],
                'Female',
                person_case_obj.get_case_property('is_pregnant'),
                case[11],
                person_case_obj.get_case_property('aadhar_number'),
                case_obj.get_case_property('has_bank_account'),
                case_obj.get_case_property('bank_ifsc_code'),
                case_obj.get_case_property('bank_account_number'),
                case_obj.get_case_property('bank_name'),
                case[9]
            ]
            data_rows.append(row)

        fout = open('/home/cchq/Bihar_bank_account_adhaar_data.csv', 'w')

        writer = csv.writer(fout)
        writer.writerows(data_rows)
