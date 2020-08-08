from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dateutil import parser
import csv
from datetime import date

case_accessor = CaseAccessors('icds-cas')
awcs = [
    {
        'awc_id':'edd091dafb6a8a01adb93c99a2679a69',
        'awc_name': 'Mahuda 01',
        'awc_site_code': '22409080401'
    },
    {
        'awc_id':'edd091dafb6a8a01adb93c99a2679133',
        'awc_name': 'Mahuda 02',
        'awc_site_code': '22409080402'
    }
    ,{
        'awc_id': 'edd091dafb6a8a01adb93c99a2678bb6',
        'awc_name': 'Mahuda 03',
        'awc_site_code': '22409080403'
    },
    {
        'awc_id':'edd091dafb6a8a01adb93c99a26780a2',
        'awc_name': 'Mahuda 04',
        'awc_site_code': '22409080404'
    },
    {
        'awc_id':'edd091dafb6a8a01adb93c99a26772b5',
        'awc_name': 'Mahuda 05',
        'awc_site_code': '22409080405'
    }
]


headers = [
    'Name of Project',
    'Anganwadi Center Name',
    'Name of Village',
    'Anganwadi Center Code',
    'Household ID',
    'Household Name',
    'Name',
    'Age',
    'DOB',
    'Gender',
    'RCH_ID',
    'MCTS_ID',
    'Phone_Number',
    'Marital Status',
    'Age at Marriage',
    'Is Disabled',
    'Disability Type',
    'Father Name',
    'Mother Name',
    'Husband Name'
            ]

data_rows = [headers]


def calculate_age(born):
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def fetch_case_properties(case, awc):
    return [
        'JAMGAON M',
        awc['awc_name'],
        awc['awc_name'],
        awc['awc_site_code'],
        case.get_parent()[0].get_case_property('case_id'),
        case.get_parent()[0].get_case_property('name'),
        case.get_case_property('name'),
        calculate_age(parser.parse(case.get_case_property('dob'))),
        case.get_case_property('dob'),
        case.get_case_property('sex'),
        case.get_case_property('rch_id'),
        case.get_case_property('mcts_id'),
        case.get_case_property('phone_number'),
        case.get_case_property('marital_status'),
        case.get_case_property('age_marriage'),
        case.get_case_property('disabled'),
        case.get_case_property('disability_type'),
        case.get_case_property('father_name'),
        case.get_case_property('mother_name'),
        case.get_case_property('husband_name'),
    ]

for awc in awcs:
    case_ids = case_accessor.get_open_case_ids_in_domain_by_type('person',[awc['awc_id']])


    cases = case_accessor.get_cases(case_ids)

    for case in cases:
        if case.get_case_property('migration_status')!='migrated':
            row = fetch_case_properties(case, awc)
            data_rows.append(row)


fout = open('/home/cchq/Mahuda_person_case_data.csv','w')

writer = csv.writer(fout)
writer.writerows(data_rows)
