import csv
from datetime import date, timedelta

from custom.icds_reports.models.aggregate import AwcLocation
from dateutil import parser

from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.view_helpers import get_case_hierarchy
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors

case_accessor = CaseAccessors('icds-cas')
ls = LedgerAccessors('icds-cas')

awcs = AwcLocation.objects.filter(aggregation_level=5, state_id='f98e91aa003accb7b849a0f18ebd7039',
                                  district_id='e247afa5d0f248b9bbdba45bb279366c',
                                  block_id='3c9e7afe194647fc818543bfddf01729').values('doc_id',
                                                                                      'awc_site_code',
                                                                                      'awc_name',
                                                                                      'supervisor_name')
x = SQLProduct.by_domain('icds-cas')
default_value = date(1970, 1, 1)

vaccine_ID_name = [(f.product_id, f.name) for f in x]

vaccine_names = [v[1] for v in vaccine_ID_name]

headers = [
              'Name of Sector',
              'Anganwadi Center Name',
              'Name of Village',
              'Anganwadi Center Code',
              'wardNumber1',
              'wardNumber2',
              'wardNumber3',
              'Household ID',
              'Household Name',
              'HH Registration Date',
              'Caste',
              'BPL/APL',
              'Minority',
              'HH Number FROM HH CASE',
              'Religion',
              'Name',
              'Aadhar Present',
              'Age at Registration',
              'Age',
              'DOB',
              'Sex',
              'RCH_ID',
              'MCTS_ID',
              'Phone_Number',
              'Marital Status',
              'Age at Marriage',
              'Is Disabled',
              'Disability Type',
              'Father Name',
              'Mother Name',
              'Husband Name',
              'Referral Status',
              'Resident',
              'Alive',
              'Closed_date',
              'HH GPS Location FROM HH CASE',
              'HH Member Number FROM PERSON CASE',
              'HH HEAD',
              'HH HEAD NAME',
              'PERSON CASE ID',
              'is_pregnant',
              'private_admit',
              'primary_admit',
              'blood_group',
              'last_preg_tt',
              'case_type',
              'age_marriage',
              'preg_order',
              'last_referral_date',
              'has_bank_account',
              'referral_health_problem',
              'referral_reached_date',
              'referral_reached_facility',
              'date_primary_admit',
              'date_return_private',
              'date_last_private_admit',
              'primary_school_admit',
              'is_oos',
              'last_class_attended_ever',
              'was_oos_ever',
              'time_birth',
              'child_alive',
              'last_reported_fever_date',
              'date_death'
              'Bank Account Number'
              'IFSC COde',
              'ICDS Services',
              'LMP',
              'Hb',
              'ActualDateOfDelivery',
              'TermDays (ChildDateOfBirth-LMP)',
              'TypeofBirth'
              'TT1Date',
              'TT2Date',
              'TTBoosterDate',
              'mother_id',
              'father_id',
              'husband_id'
          ] + vaccine_names

data_rows = [headers]


def calculate_age(born):
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def get_father_name(val):
    if val and len(val) == 36:
        case = case_accessor.get_cases([val])[0]
        return case.get_case_property('name')
    else:
        return val


def get_household_case(case):
    for parent in case.get_parent():
        if parent.get_case_property('type') == 'household':
            return parent


def if_mother(child_Cases):
    for case in child_Cases:
        if case['case'].type == 'ccs_record':
            return case['case']
    return False


def if_child(child_Cases):
    for case in child_Cases:
        if case['case'].type == 'child_health':
            return case['case']
    return False


def if_task(child_Cases):
    for case in child_Cases:
        if case['case'].type == 'tasks':
            return case['case']
    return False


def get_task_Case(child_Cases):
    mother = if_mother(child_Cases)
    child = if_child(child_Cases)
    descendent = None
    if mother:
        descendent = mother
    elif child:
        descendent = child

    related_cases = []
    if descendent:
        related_cases = get_case_hierarchy(descendent, {})

    if not related_cases:
        return None

    child_Cases = related_cases['child_cases']
    return if_task(child_Cases)


def fill_vaccine(ledgers):
    ld = ledgers if ledgers else []

    leds = {led.entry_id: led for led in ld}
    total_vacs = []
    for vac in vaccine_ID_name:
        vacci = leds.get(vac[0])

        if vacci:
            total_vacs.append((default_value + timedelta(vacci.balance)))
        else:
            total_vacs.append('')

    return total_vacs


def get_mother(case):
    for parent in case.get_parent():
        if parent.get_case_property('type') == 'person':
            return parent


def get_father_id(case):
    father_name = case.get_case_property('father_name')
    for parent in case.get_parent():
        if parent.get_case_property('type') == 'household':
            related_cases = get_case_hierarchy(parent, {})

            for parent_person_case in related_cases['child_cases']:
                if parent_person_case['case'].get_case_property('name') == father_name:
                    return parent_person_case['case'].get_case_property('case_id')
    return ''


def get_husband_id(case):
    husband_name = case.get_case_property('husband_name')
    for parent in case.get_parent():
        if parent.get_case_property('type') == 'household':
            related_cases = get_case_hierarchy(parent, {})

            for parent_person_case in related_cases['child_cases']:
                if parent_person_case['case'].get_case_property('name') == husband_name:
                    return parent_person_case['case'].get_case_property('case_id')
    return ''


def commcare_user_case(case):
    aww_user_id = case.opened_by
    case_ids = case_accessor.get_open_case_ids_in_domain_by_type('commcare-user', [aww_user_id])
    return case_accessor.get_case(case_ids[0])


def fetch_case_properties(case, child_Cases, awc):
    mother = if_mother(child_Cases)
    task_case = get_task_Case(child_Cases)
    ledgers = None
    if task_case:
        ledgers = ls.get_ledger_values_for_case(task_case.get_case_property('case_id'))

    vaccines = fill_vaccine(ledgers)

    lmp = mother.get_case_property('lmp') if mother else ''
    add = mother.get_case_property('add') if mother else ''

    return [
               awc['supervisor_name'],
               awc['awc_name'],
               awc['awc_name'],
               awc['awc_site_code'],
               commcare_user_case(case).get_case_property('awc_ward_1'),
               commcare_user_case(case).get_case_property('awc_ward_2'),
               commcare_user_case(case).get_case_property('awc_ward_3'),
               get_household_case(case).get_case_property('case_id'),
               get_household_case(case).get_case_property('name'),
               get_household_case(case).get_case_property('hh_reg_date'),
               get_household_case(case).get_case_property('hh_caste'),
               get_household_case(case).get_case_property('hh_bpl_apl'),
               get_household_case(case).get_case_property('hh_minority'),
               get_household_case(case).get_case_property('hh_num'),
               get_household_case(case).get_case_property('hh_religion'),
               case.get_case_property('name'),
               case.get_case_property('has_aadhar'),
               case.get_case_property('age_at_reg'),
               '' if case.get_case_property('dob') is None else calculate_age(
                   parser.parse(case.get_case_property('dob'))),
               case.get_case_property('dob'),
               case.get_case_property('sex'),
               case.get_case_property('rch_id'),
               case.get_case_property('mcts_id'),
               case.get_case_property('phone_number'),
               case.get_case_property('marital_status'),
               case.get_case_property('age_marriage'),
               case.get_case_property('disabled'),
               case.get_case_property('disability_type'),
               get_father_name(case.get_case_property('father_name')),
               case.get_case_property('mother_name'),
               case.get_case_property('husband_name'),
               case.get_case_property('referral_status'),
               case.get_case_property('resident'),
               case.get_case_property('died') != 'yes',
               case.get_case_property('closed_on'),
               get_household_case(case).get_case_property('hh_gps_location'),
               case.get_case_property('hh_member_number'),
               get_household_case(case).get_case_property('hh_head'),
               get_household_case(case).get_case_property('hh_head_name'),
               case.get_case_property('case_id'),
               case.get_case_property('is_pregnant'),
               case.get_case_property('private_admit'),
               case.get_case_property('primary_admit'),
               case.get_case_property('blood_group'),
               case.get_case_property('last_preg_tt'),
               case.get_case_property('case_type'),
               case.get_case_property('age_marriage'),
               case.get_case_property('preg_order'),
               case.get_case_property('last_referral_date'),
               case.get_case_property('has_bank_account'),
               case.get_case_property('referral_health_problem'),
               case.get_case_property('referral_reached_date'),
               case.get_case_property('referral_reached_facility'),
               case.get_case_property('date_primary_admit'),
               case.get_case_property('date_return_private'),
               case.get_case_property('date_last_private_admit'),
               case.get_case_property('primary_school_admit'),
               case.get_case_property('is_oos'),
               case.get_case_property('last_class_attended_ever'),
               case.get_case_property('was_oos_ever'),
               case.get_case_property('time_birth'),
               case.get_case_property('child_alive'),
               case.get_case_property('last_reported_fever_date'),
               case.get_case_property('date_death'),
               case.get_case_property('bank_account_number'),
               case.get_case_property('ifsc_code'),
               case.get_case_property('registered_status'),
               lmp,
               mother.get_case_property('anemia') if mother else '',
               add,
               parser.parse(add) - parser.parse(lmp) if lmp and add and len(lmp) > 0 and len(add) > 0 else '',
               mother.get_case_property('delivery_nature') if mother else '',
               task_case.get_case_property('tt_complete_date') if mother and task_case else '',
               task_case.get_case_property('tt_complete_date') if mother and task_case else '',
               task_case.get_case_property('tt_complete_date') if mother and task_case else '',
               get_mother(case).get_case_property('case_id') if if_child(child_Cases) else '',
               get_father_id(case),
               get_husband_id(case)
           ] + vaccines


for awc in awcs:
    case_ids = case_accessor.get_open_case_ids_in_domain_by_type('person', [awc['doc_id']])
    cases = case_accessor.get_cases(case_ids)

    for case in cases:
        if case.get_case_property('migration_status') != 'migrated':
            related_cases = get_case_hierarchy(case, {})
            child_Cases = related_cases['child_cases']
            row = fetch_case_properties(case, child_Cases, awc)
            data_rows.append(row)

fout = open('/home/cchq/Kaika_person_case_data.csv', 'w')

writer = csv.writer(fout)
writer.writerows(data_rows)
