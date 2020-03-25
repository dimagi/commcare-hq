from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dateutil import parser
import csv

from custom.icds_reports.models.aggregate import AwcLocation
from corehq.apps.reports.view_helpers import get_case_hierarchy
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.apps.products.models import SQLProduct
from datetime import date, timedelta


case_accessor = CaseAccessors('icds-cas')
ls = LedgerAccessors('icds-cas')

awcs = AwcLocation.objects.filter(aggregation_level=5, state_id='f9b47ea2ee2d8a02acddeeb491d3e175').values('doc_id',
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
    'Name',
    'Phone_Number'
    'case_type',
    'has_bank_account',
    'Bank Account Number'
    'IFSC COde']

data_rows = [headers]


def fetch_case_properties(case, awc):

    return [
        awc['supervisor_name'],
        awc['awc_name'],
        awc['awc_name'],
        awc['awc_site_code'],
        case.get_case_property('name'),
        case.get_case_property('phone_number'),
        case.get_case_property('case_type'),
        case.get_case_property('has_bank_account'),
        case.get_case_property('bank_account_number'),
        case.get_case_property('ifsc_code')
    ]


for awc in awcs:
    case_ids = case_accessor.get_open_case_ids_in_domain_by_type('ccs_record',[awc['doc_id']])
    cases = case_accessor.get_cases(case_ids)

    for case in cases:
        if case.get_case_property('migration_status') != 'migrated':
            related_cases = get_case_hierarchy(case, {})
            child_Cases = related_cases['child_cases']
            row = fetch_case_properties(case, awc)
            data_rows.append(row)


fout = open('/home/cchq/Bihar_bank_account_data.csv','w')

writer = csv.writer(fout)
writer.writerows(data_rows)