from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
import csv

from custom.icds_reports.models.aggregate import AwcLocation

headers = [
	'StateID',
	'StateName'
	'DistrictID',
	'DistrictName',
	'ProjectID',
	'ProjectName',
	'SectorID',
	'SectorName',
	'AWCID',
	'AWCName',
	'Name',
	'Phone_Number'
	'Has Bank Account?',
	'Bank IFSC Code',
	'Bank Account Number',
	'Bank Name',
	'Bank branch name']

data_rows = [headers]

def get_person_case(case):
	for parent in case.get_parent():
		if parent.get_case_property('person')=='person':
			return parent


def fetch_case_properties(case, awc):
	return [
    	awc['state_site_code'],
    	awc['state_name'],
    	awc['district_site_code'],
    	awc['district_name'],
    	awc['block_site_code'],
    	awc['block_name']
        awc['supervisor_site_code'],
    	awc['supervisor_name'],
        awc['awc_site_code'],
        awc['awc_name'],
        get_person_case.get_case_property('name'),
        get_person_case.get_case_property('contact_phone_number'),
        case.get_case_property('has_bank_account'),
        case.get_case_property('bank_ifsc_code'),
        case.get_case_property('bank_account_number'),
        case.get_case_property('bank_name'),
        case.get_case_property('bank_branch_name')
    ]


class Command(BaseCommand):
    help = "Run Bihar Data Pull"

    def handle(self, **options):
        case_accessor = CaseAccessors('icds-cas')

        awcs = AwcLocation.objects.filter(aggregation_level=5,
                                          state_id='f9b47ea2ee2d8a02acddeeb491d3e175').values(
            'doc_id', 'state_site_code', 'state_name', 'district_site_code',
            'district_site_code', 'block_site_code', 'block_name', 'supervisor_site_code',
            'supervisor_name', 'awc_site_code', 'awc_name')
        for awc in awcs:
            case_ids = case_accessor.get_open_case_ids_in_domain_by_type('ccs_record', [awc['doc_id']])
            cases = case_accessor.get_cases(case_ids)

            for case in cases:
                if get_person_case(case).get_case_property('migration_status') != 'migrated':
                    row = fetch_case_properties(case, awc)
                    data_rows.append(row)

        fout = open('/home/cchq/Bihar_bank_account_data.csv', 'w')

        writer = csv.writer(fout)
        writer.writerows(data_rows)


