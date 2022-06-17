import datetime
import textwrap

from jsonobject.api import re_date

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.parsing import json_format_date

from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_missing,
    exact_case_property_text_query,
)
from corehq.util.dates import iso_string_to_date
from custom.covid.management.commands.update_cases import CaseUpdateCommand


class Command(CaseUpdateCommand):
    help = textwrap.dedent("""
        Twice-off script created 2022-02-03, updated 2022-02-11. A bunch of
        cases had the property all_activity_complete_date inadvertently set to
        the string 'date(today())' rather than a date. This blanked that out.
        Later, it was determined an integration doesn't handle blank values
        well, so this now finds those cases that were blanked out and sets them
        to an actual date.
    """)

    logger_name = __name__

    def find_case_ids(self, domain):
        query = (CaseSearchES()
                .domain(domain)
                .filter(exact_case_property_text_query('current_status', 'closed'))
                .filter(case_property_missing("all_activity_complete_date"))
                .case_type(self.case_type)
                .owner(INACTIVE_LOCATION_IDS))

        if self.case_type == 'contact':
            query = (query.modified_range(gte=datetime.date(2022, 2, 2))
                .NOT(
                    exact_case_property_text_query('final_disposition', 'converted_to_pui')
            ))

        return list(query.scroll_ids())

    def case_blocks(self, case):
        if (
                # Double check filters in case ES data is stale
                case.get_case_property('all_activity_complete_date')
                or case.get_case_property('current_status') != 'closed'
                or (case.type == 'contact'
                    and case.get_case_property('final_disposition') == 'converted_to_pui')
                or case.owner_id not in INACTIVE_LOCATION_IDS
        ):
            return None

        self.logger.debug(f"_correct_bad_case_property {case.domain} {case.case_id}")
        date_func = _get_new_contact_date_value if case.type == 'contact' else _get_new_patient_date_value
        new_value = date_func(case)
        return [CaseBlock(
            create=False,
            case_id=case.case_id,
            update={"all_activity_complete_date": new_value},
        )]


def _get_new_patient_date_value(case):
    return _get_new_date_value(
        case,
        ['closed_date', 'isolation_end_date', 'quarantine_end_date'],
        ['symptom_onset_date', 'new_lab_result_specimen_collection_date', 'specimen_collection_date', 'opened_on']
    )


def _get_new_contact_date_value(case):
    return _get_new_date_value(
        case,
        ['closed_date', 'quarantine_end_date'],
        ['exposure_date', 'fup_next_call_date', 'opened_on']
    )


def _get_new_date_value(case, plain_date_props, adjust_date_props):
    def _is_date(value):
        return value and (isinstance(value, datetime.date) or re_date.match(value))

    found_prop, found_value = None, None
    for prop in plain_date_props + adjust_date_props:
        value = case.get_case_property(prop)
        if _is_date(value):
            found_prop, found_value = prop, value
            break

    if found_prop in adjust_date_props:
        date_value = iso_string_to_date(found_value) if isinstance(found_value, str) else found_value
        adjusted_date_value = date_value + datetime.timedelta(days=15)
        return json_format_date(adjusted_date_value)
    return found_value


INACTIVE_LOCATION_IDS = [
    '9074edfe555043fd8f16825a6236a313',
    '62c7aa16b77140b98ed1e4d09ae0b756',
    'de98c400ca394099be014e632d3e342e',
    '21a9e05ff2ee4e468d7d69b66f537d06',
    '38eec5e54108404d86779e4d5735f42e',
    '6840086194254414b89854125f5c84d1',
    '0ff93180c3a44e8f860213f9f15c46a1',
    'f36d29ae1c29442988f27cdb87e6cb9f',
    '35bb743c0af14ed797054a633aaac4a7',
    'db0ebafbf7e24b2387eb12a1f5b116ba',
    '009b98aac229405688be47bd60569465',
    'ab883ee22aed4962bfdab2032e55ef4f',
    '0184901e04054c45b86be7210952dc5f',
    'b02aed10be34410f9fb27247ec0bbf88',
    'c7a5639716aa4b3eaceb6c26300ac636',
    'd32cbde5383c40ea8570222a58df1f57',
    '7880d1a174c0442189395a38d5aa3eed',
    '6e9e6280776e44fb82b6844c5e543254',
    'cee3dc5061b34f048f2057fa1dde9520',
    'a899f294bdab47b9911bc95fa407d641',
    '4956529fb3534f9a8b1296d2d64f173f',
    '5a6409666eec4d3dadb59864e82314af',
    'cee8594870e045d5acbbc5baacbce677',
    '1984b807bd8246968a1c9c1aaf852a8f',
    '69f546be9f26429cb17cd6f008279dc9',
    '12958635046d4e4eae3d1236217a7cb8',
    '48b07d59372745edb62d1fd2ace63856',
    'd440460e27404d35b385b3b7de174349',
    '986d1724ec0c4e6791e18efada2c4876',
    '6a732bd91abf4640a5a43e00705bea75',
    'd407b7af31bc4284b22f43ca30537faf',
    'e90b03868bdb472987a04e1e3854d9ba',
    'fccebb04f82c4ed3b6e96ed2b70791c2',
    'c794ee8e2ac14b029e317e6d229bf82b',
    'd1885ac098424d94a3cae6f4a5ea5fac',
    'be411ad04eb94e51be51d47d741c3e59',
    '10f8038c7d904391837a861f523b945f',
    '41a7a599ddb44636946a57847d373820',
    '94eaa48f839243cf85b953a181d016a3',
    '92747c2446024381a2acd7a3912c824f',
    'e24875dc72ef4b9995d4d272fe17ca35',
    '092a985d390a4b8fa114daacb4a61117',
    'f423aedcdb8c4bdaaf5a95165b70481f',
    '7a8116e2ab164821ab45bf2c0968d644',
    '3537604285a14f3c98b867671c988b1d',
    'a83b9f69af6544d9bdbb0e7e1bea0a15',
    '7ecc4d6a8c544d42862701b572d75cbd',
    '6ac85f598f3343a2aa730e742bf1c2e1',
    'e73f8fd2626e48a3a5369e9b177beb81',
    '74660120f439484c8c6918522d83e0c2',
    '240ae98bd84e4d95b7f50a3d89567937',
    '2954a873a4094ba0af8b16822caf1656',
    'db33040a54e543eb8c340fb192d74fa3',
    'a29f7fbb8df745f48f2f2cd5c7bdb245',
    'b63fa6c57aaa4e6cba16b919e7c2f408',
    'ce18fd8ddac14be686e7ffb8755377be',
    '4546387a1819439196edf4a52e5d121a',
    'e07d0bbaccbb4bde8f37a77fc9926359',
    '99560c995f9d44b08873de78e7b92b74',
    'c5395b938b044c92957dc0a1c457c6ab',
    '02d287bb6685455eab691d770c6bafbc',
    '569b53a60c9b4fd5aadeb878a715a60e',
    '0466344625eb4223a8f7bc93516d9de5',
    'ced235a967064d4b8da251759abc9791',
    '9c70aa3d87694ec3b82c278501ba489b',
]
