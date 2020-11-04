#!/usr/bin/env python3
"""
A utility script for fetching data set IDs, and printing
``CASE_PROPERTY_MAP`` items in the format used by ``tasks.py``.

``DATA_ELEMENTS_TSV`` is a string that you might get from copy-pasting
from a spreadsheet of case property, data element name, data element ID
rows.
"""
import requests


BASE_URL = 'https://play.dhis2.org/dev'
USERNAME = 'admin'
PASSWORD = 'district'
DATA_ELEMENTS_TSV = """
dhis_hmis_data_discussed	HMIS Management meetings conducted	krUiCzsUAZr
dhis_admissions_in_quarter	HMIS Total # of Admissions (including Maternity)	yCJBWuhuOLc
dhis_suspected_malaria_cases_under_5yrs	HMIS17 Malaria Under 5 years  Admissions	ttpMSWCCq6s
dhis_total_budget_for_drugs	HMIS Cumulative drug budget	P0YGSCM0OKb
dhis_expenditure_in_quarter	HMIS17 Cumulative actual expenditure in all programmes	M2Pkr4zxryN
dhis_health_facilities_under_hospital_management_supervision	ENVT EH # Of Health Facilities In The  District	M3HHFh3RDNP
dhis_quarterly_estimated_pregnant_women_in_area	CHD EPI Pregnant women	GxqYLY3iWcz
dhis_ambulances_functional	HMIS # of Functioning Ambulances	MRqq82xATzI
dhis_what_is_the_total_number_of_beds_at_the_facility	HMIS Bed Capacity	asCqjKclllu
dhis_quarterly_estimated_children_under_5_in_area	CMED Under 5 Population	PVYgza4lLfj
dhis_prev_new_smear_positive_cases_cured	TBTO New Smear Positive Cured	gKghGP99qDe
dhis_prev_new_smear_positive_cases_dead	TBTO New Smear Positive Died	yssWGMYDkdA
dhis_prev_new_smear_positive_cases_treatment_failure	TBTO New Smear Positive Failure	dmyxAlzfCiK
dhis_prev_new_eptb_cases_cured	TB New Treatment outcome New EPTB Cured	a8nx11YujJz
dhis_prev_new_eptb_cases_treatment_completed	TB New Treatment outcome New EPTB Treatment completed	NFRHK1cgHrc
dhis_prev_new_eptb_cases_dead	TBTO EPTB Died	dzRlRptoj38
dhis_prev_new_eptb_cases_treatment_failure	TB New Treatment outcome New EPTB Treatment failed	wNKjjozXyQY
dhis_sputum_collection_points	TB COMM Number of Sputum sample collection points in the catchment	BU493LnfBTD
dhis_sputum_collection_points_functioning	TB COMM Number of Functional Sputum sample collection points in the catchment	GhUn5j5ajzK
dhis_hiv_ve_clients_on_art	NCD CC HIV Status +Ve on ART	E2TaryAVqeT
dhis_village_clinics	CHD IMCI # of Functional Village Clinics Within Catchment	gtLvoz94gur
dhis_cbdas	HTS Number of CBDA/HSA	LGaHPDsUydT
dhis_village_health_committees	HMIS HM Active village health committees within catchment area	J7fogdejE3j
dhis_households_with_improved_latrines	ENVT EH # Of Households Owning And Using Improved Sanitary Facilities	u5erlSYbxTU
dhis_households_access_to_clean_water	HMIS # of Households with Access to Safe Drinking Water	BDzMvX3y7Kc
"""


def get_data_elements():
    """
    Yields [case property, data element name, data element ID]
    """
    for line in DATA_ELEMENTS_TSV.split('\n'):
        if line:
            yield line.split('\t')


def main():
    for case_prop, de_name, de_id in get_data_elements():
        url = f'{BASE_URL}/api/dataElements/{de_id}.json'
        auth = (USERNAME, PASSWORD)
        resp = requests.get(url, auth=auth, verify=False)
        if resp.status_code == 404:
            print(f'    # {de_name} ({de_id}) not found')
            continue
        data_set_id = resp.json()['dataSetElements'][0]['dataSet']['id']
        print(f"""    '{case_prop}': DataElement(
        id='{de_id}',  # {de_name}
        data_set='{data_set_id}',
    ),""")


if __name__ == '__main__':
    main()
