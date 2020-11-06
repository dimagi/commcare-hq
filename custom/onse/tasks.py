"""
Importing aggregated data from DHIS2
====================================

The ``update_facility_cases_from_dhis2_data_elements()`` task is
*custom* code because it is unusual, in that it imports aggregated data,
and saves it to case properties. One would expect to import instance
data to instances, not aggregated data. A future DHIS2 Importer will
import tracked entity instances.

.. IMPORTANT::
   This code selects a ``ConnectionSettings`` instance by name, and
   assumes that it exists! See ``CONNECTION_SETTINGS_NAME`` below.


I'm a TFM. What do I do?
------------------------

If you are reading this, it's probably because something has changed in
DHIS2 or a CommCare app, you need to change the configuration. See
``CASE_PROPERTY_MAP`` below. It is a list of case properties, each one
mapped to a DHIS2 data element, and a data set that the data element
belongs to. e.g. ::

    'dhis_hmis_data_discussed': DataElement(
        id='krUiCzsUAZr',  # HMIS Management meetings conducted
        data_set='q1Es3k3sZem',
    ),

In this example, "dhis_hmis_data_discussed" is the case property name.
You can find the ID of the data element in DHIS2, under "Maintenance" >
"Data Element" > "List", by searching for its name ("HMIS Management
meetings conducted"). Click the "Action" icon (⋮) on the right and
choose "Show details" to find the ID. There you will also find "API
URL". Open that, and read down to "dataSetElements" > 0 > "dataSet" >
"id" to get the data set ID.

You or a developer can update this file with your changes, and PR,
merge, and deploy it, to implement the changes.


I'm a dev. What is this code?
-----------------------------

This code uses the ``get_case_blocks()`` generator to iterate through
``CASE_TYPE`` cases in the ``DOMAIN`` domain ("facility_supervision" and
"onse-iss" at the time of writing). For each one, it yields a
``CaseBlock`` for updating the case.

The ``set_case_updates()`` generator consumes the ``CaseBlock``s. Each
case corresponds to a facility *organisation unit* in DHIS2. For each
case property in ``CASE_PROPERTY_MAP`` the function fetches its
corresponding *data element*'s *data set* from DHIS2.

.. NOTE::
   A *data set* is a collection of related aggregated indicators called
   *data elements*. Some *data elements* are broken down by *category
   options*. e.g. In DHIS2 demo data, the *data element* "Live births"
   is broken down by the *category* "Gender", which is given with the
   *category options* "Female" and "Male". The "Life births" *data
   element* belongs to the "Reproductive Health" *data set*. When we
   fetch the *data set*, the "Live births" *data element* may be
   returned with separate counts for the "Female" *category option* and
   the "Male" *category option*. We must take the count for each
   *category option* and sum them to get the total for the *data
   element*.

``set_case_updates()`` sets the case property value to the total of the
counts for all *category options* of the case property's *data element*.

Finally, the ``save_cases()`` function saves the ``CaseBlock``s in
chunks of 1000.

"""
from collections import namedtuple
from datetime import date
from typing import Iterable, Optional

from celery.schedules import crontab
from celery.task import periodic_task

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.models import ConnectionSettings
from corehq.util.soft_assert import soft_assert

DataElement = namedtuple('DataElement', ['id', 'data_set'])

# Map CommCare case properties to DHIS2 data elements
CASE_PROPERTY_MAP = {
    'dhis_hmis_data_discussed': DataElement(
        id='krUiCzsUAZr',  # HMIS Management meetings conducted
        data_set='q1Es3k3sZem',
    ),
    'dhis_admissions_in_quarter': DataElement(
        id='yCJBWuhuOLc',  # HMIS Total # of Admissions (including Maternity)
        data_set='q1Es3k3sZem',
    ),
    'dhis_suspected_malaria_cases_under_5yrs': DataElement(
        id='ttpMSWCCq6s',  # HMIS17 Malaria Under 5 years  Admissions
        data_set='uk3Vkwy5cIe',
    ),
    'dhis_total_budget_for_drugs': DataElement(
        id='P0YGSCM0OKb',  # HMIS Cumulative drug budget
        data_set='q1Es3k3sZem',
    ),
    'dhis_expenditure_in_quarter': DataElement(
        id='M2Pkr4zxryN',  # HMIS17 Cumulative actual expenditure in all programmes
        data_set='uk3Vkwy5cIe',
    ),
    'dhis_health_facilities_under_hospital_management_supervision': DataElement(
        id='M3HHFh3RDNP',  # ENVT EH # Of Health Facilities In The  District
        data_set='iTo9FkAJTSl',
    ),
    'dhis_quarterly_estimated_pregnant_women_in_area': DataElement(
        id='GxqYLY3iWcz',  # CHD EPI Pregnant women
        data_set='XcgwcDqqE17',
    ),
    'dhis_ambulances_functional': DataElement(
        id='MRqq82xATzI',  # HMIS # of Functioning Ambulances
        data_set='q1Es3k3sZem',
    ),
    'dhis_what_is_the_total_number_of_beds_at_the_facility': DataElement(
        id='asCqjKclllu',  # HMIS Bed Capacity
        data_set='q1Es3k3sZem',
    ),
    'dhis_quarterly_estimated_children_under_5_in_area': DataElement(
        id='PVYgza4lLfj',  # CMED Under 5 Population
        data_set='rkyO2EAX45C',
    ),
    'dhis_prev_new_smear_positive_cases_cured': DataElement(
        id='gKghGP99qDe',  # TBTO New Smear Positive Cured
        data_set='VEqRXwmqhM1',
    ),
    'dhis_prev_new_smear_positive_cases_dead': DataElement(
        id='yssWGMYDkdA',  # TBTO New Smear Positive Died
        data_set='VEqRXwmqhM1',
    ),
    'dhis_prev_new_smear_positive_cases_treatment_failure': DataElement(
        id='dmyxAlzfCiK',  # TBTO New Smear Positive Failure
        data_set='VEqRXwmqhM1',
    ),
    'dhis_prev_new_eptb_cases_cured': DataElement(
        id='a8nx11YujJz',  # TB New Treatment outcome New EPTB Cured
        data_set='fOiOJU7Vt2n',
    ),
    'dhis_prev_new_eptb_cases_treatment_completed': DataElement(
        id='NFRHK1cgHrc',  # TB New Treatment outcome New EPTB Treatment completed
        data_set='fOiOJU7Vt2n',
    ),
    'dhis_prev_new_eptb_cases_dead': DataElement(
        id='dzRlRptoj38',  # TBTO EPTB Died
        data_set='VEqRXwmqhM1',
    ),
    'dhis_prev_new_eptb_cases_treatment_failure': DataElement(
        id='wNKjjozXyQY',  # TB New Treatment outcome New EPTB Treatment failed
        data_set='fOiOJU7Vt2n',
    ),
    # TB COMM Number of Sputum sample collection points in the catchment (BU493LnfBTD) not found
    # TB COMM Number of Functional Sputum sample collection points in the catchment (GhUn5j5ajzK) not found
    # NCD CC HIV Status +Ve on ART (E2TaryAVqeT) not found
    'dhis_village_clinics': DataElement(
        id='gtLvoz94gur',  # CHD IMCI # of Functional Village Clinics Within Catchment
        data_set='hWDsGIjs16g',
    ),
    'dhis_cbdas': DataElement(
        id='LGaHPDsUydT',  # HTS Number of CBDA/HSA
        data_set='wLQlOnKX6yN',
    ),
    'dhis_village_health_committees': DataElement(
        id='J7fogdejE3j',  # HMIS HM Active village health committees within catchment area
        data_set='q1Es3k3sZem',
    ),
    'dhis_households_with_improved_latrines': DataElement(
        id='u5erlSYbxTU',  # ENVT EH # Of Households Owning And Using Improved Sanitary Facilities
        data_set='iTo9FkAJTSl',
    ),
    'dhis_households_access_to_clean_water': DataElement(
        id='BDzMvX3y7Kc',  # HMIS # of Households with Access to Safe Drinking Water
        data_set='q1Es3k3sZem',
    ),
}

DOMAIN = 'onse-iss'
CASE_TYPE = 'facility_supervision'
CONNECTION_SETTINGS_NAME = 'DHIS2 Facilities Import Server'


_soft_assert = soft_assert('@'.join(('nhooper', 'dimagi.com')))


@periodic_task(
    # Run on the 5th day of every quarter
    run_every=crontab(day_of_month=5, month_of_year='1,4,7,10',
                      hour=22, minute=30),
    queue='background_queue',
)
def update_facility_cases_from_dhis2_data_elements():
    try:
        dhis2_server = ConnectionSettings.objects.get(
            domain=DOMAIN, name=CONNECTION_SETTINGS_NAME
        )
    except ConnectionSettings.DoesNotExist:
        _soft_assert(False, (
            f'ConnectionSettings {CONNECTION_SETTINGS_NAME!r} not found in '
            f'domain {DOMAIN!r} for importing DHIS2 data elements.'))
        return

    facility_case_blocks = get_case_blocks()
    facility_case_blocks = set_case_updates(dhis2_server, facility_case_blocks)
    save_cases(facility_case_blocks)


def get_case_blocks() -> Iterable[CaseBlock]:
    case_accessors = CaseAccessors(DOMAIN)
    for case_id in case_accessors.get_case_ids_in_domain(type=CASE_TYPE):
        case = case_accessors.get_case(case_id)
        if not case.external_id:
            # This case is not mapped to a facility in DHIS2.
            continue
        case_block = CaseBlock(
            case_id=case.case_id,
            external_id=case.external_id,
            case_type=CASE_TYPE,
            case_name=case.name,
            update={},
        )
        yield case_block


def set_case_updates(
    connection_settings: ConnectionSettings,
    case_blocks: Iterable[CaseBlock]
) -> Iterable[CaseBlock]:
    """
    Fetch all the data elements for the data set, because we don't know
    in advance what category option combos to query for
    """
    # e.g. https://play.dhis2.org/dev/api/dataValueSets?orgUnit=jNb63DIHuwU
    #   &period=2020Q2
    #   &dataSet=QX4ZTUbOt3a  <-- The data set of the data element
    # not https://play.dhis2.org/dev/api/dataValues?ou=jNb63DIHuwU
    #   &pe=2020Q2
    #   &de=gQNFkFkObU8  <-- The data element we want
    #   &co=L4P9VSgHkF6  <-- We don't know this, and without it we get a 409
    requests = connection_settings.get_requests()
    endpoint = '/api/dataValueSets'
    params = {'period': get_last_quarter()}
    for case_block in case_blocks:
        params['orgUnit'] = case_block.external_id
        data_set_cache = {}
        for case_property, (data_element, data_set) in CASE_PROPERTY_MAP.items():
            if data_set not in data_set_cache:
                params['dataSet'] = data_set
                response_json = requests.get(endpoint, params).json()
                data_set_cache[data_set] = response_json.get('dataValues', None)

            if data_set_cache[data_set] is None:
                # No data for this facility. `None` = "We don't know"
                case_block.update[case_property] = None
            else:
                value = 0
                for data_value in data_set_cache[data_set]:
                    if data_value['dataElement'] == data_element:
                        value += int(data_value['value'])
                case_block.update[case_property] = value
        yield case_block


def get_last_quarter(today: Optional[date] = None) -> str:
    """
    Returns the last quarter in  DHIS2 web API `period format`_.
    e.g. "2004Q1"

    .. _period format: https://docs.dhis2.org/master/en/developer/html/webapi_date_perid_format.html
    """
    if today is None:
        today = date.today()
    year = today.year
    last_quarter = (today.month - 1) // 3
    if last_quarter == 0:
        year -= 1
        last_quarter = 4
    return f"{year}Q{last_quarter}"


def save_cases(case_blocks):
    today = date.today().isoformat()
    for chunk in chunked(case_blocks, 1000, collection=list):
        submit_case_blocks(
            [cb.as_text() for cb in chunk],
            DOMAIN,
            xmlns='http://commcarehq.org/dhis2-import',
            device_id=f"dhis2-import-{DOMAIN}-{today}",
        )
