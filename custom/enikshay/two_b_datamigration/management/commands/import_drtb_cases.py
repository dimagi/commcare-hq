import logging

import datetime
import uuid

from dateutil.parser import parse
from django.core.management import (
    BaseCommand,
)
from django.db import models

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation
from corehq.util.workbook_reading import open_any_workbook
from custom.enikshay.case_utils import CASE_TYPE_PERSON, CASE_TYPE_OCCURRENCE

logger = logging.getLogger('tow_b_datamigration')


# Map format is: MDR selection criteria value -> (rft_drtb_diagnosis value, rft_drtb_diagnosis_ext_dst value)
# TODO: Fill in these Nones
SELECTION_CRITERIA_MAP = {
    "MDR sus -Pre.Treat At diagnosis(Smear+ve/-ve)": ("mdr_at_diagnosis", None),
    "EP Presumptive": (None, None),
    "MDR sus -Follow up Sm+ve": ("follow_up_sm_ve_ip", None),
    "MDR sus -Contact of MDR/RR TB": ("contact_of_mdr_rr", None),
    "MDR sus -New At diagnosis(Smear+ve/-ve)": ("mdr_at_diagnosis", None),
    "Pre XDR-MDR/RR TB at Diagnosis": ("extended_dst", "mdr_rr_diagnosis"),
    "Other": (None, None),
    "Pre XDR >4 months culture positive": ("extended_dst", None),
    "Pre XDR -Failure of MDR/RR-TB regimen": ("extended_dst", "mdr_rr_failure"),
    "MDR sus-Private Referral": ("private_referral", None),
    "MDR sus -NSP/NSN At diagnosis": (None, None),
    "PLHIV Presumptive": (None, None),
    "Pre XDR -Recurrent case of second line treatment": ("extended_dst", "recurrent_second_line_treatment"),
    "Pre XDR -Culture reversion": ("extended_dst", "culture_reversion"),
    "Paediatric Presumptive": (None, None),
    "HIV -EP TB": (None, None),
    "HIV TB (Smear+ve)": (None, None),
    "HIV TB (Smear+ve at diagnosis)": (None, None),
}


def get_case_structures_from_row(domain, row):
    person_case_properties = get_person_case_properties(domain, row)
    occurrence_case_properties = get_occurrence_case_properties(row)
    episode_case_properties = get_episode_case_properties(row)
    test_case_properties = get_test_case_properties(domain, row)
    drug_resistance_case_properties = get_drug_resistance_case_properties(row)
    followup_test_cases_properties = get_follow_up_test_case_properties(row)

    person_case_structure = get_person_case_structure(person_case_properties)

    # TODO: convert all these case properties to the appropriate linked up case structures
        # TODO: Create drug resistance cases!
        # TODO: Create secondary_owner cases


def get_person_case_structure(properties):
    owner_id = properties.pop("owner_id")
    return CaseStructure(
        case_id=uuid.uuid4().hex,
        attrs={
            "case_type": CASE_TYPE_PERSON,
            "create": True,
            "owner_id": owner_id,
            # "user_id": None,  # TODO: Is this needed?
            "update": properties,
    })


def get_occurrence_case_structure(properties, person_case_structure):
    return CaseStructure(
        case_id=uuid.uuid4().hex,
        # TODO: indices
        attrs={
            "case_type": CASE_TYPE_OCCURRENCE,
            "create": True,
            # TODO: Does this need a name?
            # TODO: owner_id
            "update": properties,  # TODO: Nick creates a lot more properties
        },
        indices=[CaseIndex(
            person_case_structure,
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type=person_case_structure.attrs['case_type'],
        )],
    )


def get_person_case_properties(domain, row):
    person_name = Mehsana2016ColumnMapping.get_value("person_name", row)
    xlsx_district_name = Mehsana2016ColumnMapping.get_value("district_name", row)
    district_name, district_id = match_district(domain, xlsx_district_name)
    properties = {
        # TODO: Do they want first_name or last_name?
        "name": person_name,
        "district_name": district_name,
        "district_id": district_id,
        "owner_id": "-",
        "current_episode_type": "confirmed_drtb"
    }
    return properties


def get_occurrence_case_properties(row):
    return {
        "current_episode_type": "confirmed_drtb"
    }


def get_episode_case_properties(row):

    report_sending_date = Mehsana2016ColumnMapping.get_value("report_sending_date", row)
    report_sending_date = clean_date(report_sending_date)

    treatment_initiation_date = Mehsana2016ColumnMapping.get_value("treatment_initiation_date", row)
    treatment_initiation_date = clean_date(treatment_initiation_date)

    treatment_card_completed_date = Mehsana2016ColumnMapping.get_value("registration_date", row)
    treatment_card_completed_date = clean_date(treatment_card_completed_date)

    properties = {
        "episode_type": "confirmed_drtb",
        "episode_pending_registration": "no",
        "is_active": "yes",
        "date_of_diagnosis": report_sending_date,
        "diagnosis_test_result_date": report_sending_date,
        "treatment_initiation_date": treatment_initiation_date,
        "treatment_card_completed_date": treatment_card_completed_date,
        "regimen_change_history": get_episode_regimen_change_history(row, treatment_initiation_date)
    }
    properties.update(get_selection_criteria_properties(row))
    if treatment_initiation_date:
        properties["treatment_initiated"] = "yes_phi"

    return properties


def get_selection_criteria_properties(row):
    selection_criteria_value = Mehsana2016ColumnMapping.get_value("mdr_selection_criteria", row)
    rft_drtb_diagnosis, rft_drtb_diagnosis_ext_dst = SELECTION_CRITERIA_MAP[selection_criteria_value]

    properties = {
        "rft_general": "drtb_diagnosis",  # TODO: Should this only be included in some instances?
    }
    if rft_drtb_diagnosis:
        properties["rft_drtb_diagnosis"] = rft_drtb_diagnosis
    if rft_drtb_diagnosis_ext_dst:
        properties["rft_drtb_diagnosis_ext_dst"] = rft_drtb_diagnosis_ext_dst
    return properties


def get_resistance_properties(row):
    property_map = {
        "Rif-Resi": ("r", "R: Res"),
        "Rif Resi+Levo Resi": ("r lfx", "R: Res\nLFX: Res"),
        "Rif Resi+Levo Resi+K Resi": ("r lfx km", "R: Res\nLFX: Res\nKM: Res"),
        "Rif Resi+K Resi": ("r km", "R: Res\nKM: Res"),
    }
    dst_result_value = Mehsana2016ColumnMapping.get_value("dst_result", row)
    if dst_result_value:
        return {
            "drug_resistance_list": property_map[dst_result_value][0],
            "result_summary_display": property_map[dst_result_value][1]
        }
    else:
        return {}


def get_episode_regimen_change_history(row, episode_treatment_initiation_date):
    put_on_treatment = Mehsana2016ColumnMapping.get_value("date_put_on_mdr_treatment", row)
    put_on_treatment = clean_date(put_on_treatment)
    value = "{}: MDR/RR".format(episode_treatment_initiation_date)
    if put_on_treatment:
        value += "\n{}: {}".format(
            put_on_treatment,
            Mehsana2016ColumnMapping.get_value("type_of_treatment_initiated", row)
        )
    return value


def get_test_case_properties(domain, row):
    facility_name, facility_id = match_facility(
        domain, Mehsana2016ColumnMapping.get_value("testing_facility", row))
    properties = {
        "testing_facility_saved_name": facility_name,
        "testing_facility_id": facility_id,
        "date_reported": Mehsana2016ColumnMapping.get_value("report_sending_date", row),
    }
    properties.update(get_selection_criteria_properties(row))
    properties.update(get_resistance_properties(row))
    return properties


def get_drug_resistance_case_properties(row):
    resistant_drugs = {
        d['drug_id']: d
        for d in get_drug_resistances_from_drug_resistance_list(row)
    }
    additional_drug_case_properties = get_drug_resistances_from_individual_drug_columns(row)
    for drug in additional_drug_case_properties:
        resistant_drugs[drug['drug_id']] = drug
    return resistant_drugs.values()


def get_drug_resistances_from_individual_drug_columns(row):
    case_properties = []
    for drug_column_key, (drug_id, drug_name) in DRUG_MAP.iteritems():
        value = Mehsana2016ColumnMapping.get_value(drug_column_key, row)
        properties = {
            "name": drug_id,
            "owner_id": "-",
            "sensitivity": convert_sensitivity(value),
            "drug_id": drug_id,
            "drug_name": drug_name,  # TODO: This property isn't in the case summary (but it is in the sheet sheel made)
        }
        case_properties.append(properties)
    return case_properties


def convert_sensitivity(sensitivity_value):
    return {
        "S": "sensitive",
        "R": "resistant",
        "Conta": "unknown",
        "": "unknown",
        None: "unknown",
    }[sensitivity_value]


def get_drug_resistances_from_drug_resistance_list(row):
    drugs = get_resistance_properties(row).get("drug_resistance_list", "").split(" ")
    case_properties = []
    for drug in drugs:
        properties = {
            "name": drug,
            "owner_id": "-",
            "sensitivity": "resistant",
            "drug_id": drug,
        }
        case_properties.append(properties)
    return case_properties


def get_follow_up_test_case_properties(row):
    properties_list = []
    for follow_up in (3, 4, 6):
        # TODO: Should I check for existance of all the values?
        if Mehsana2016ColumnMapping.get_value("month_{}_follow_up_send_date".format(follow_up), row):
            properties = {
                "date_tested": clean_date(
                    Mehsana2016ColumnMapping.get_value("month_{}_follow_up_send_date".format(follow_up), row)),
                "date_reported": clean_date(
                    Mehsana2016ColumnMapping.get_value("month_{}_follow_up_result_date".format(follow_up), row)),
                "result": clean_result(
                    Mehsana2016ColumnMapping.get_value("month_{}_follow_up_result".format(follow_up), row)),
                "test_type_value": "culture",
                "test_type_label": "culture",
                "rft_general": "follow_up_drtb",
                "rft_drtb_follow_up_treatment_month": str(follow_up)
            }
            properties["result_summary_label"] = result_label(properties['result'])

            properties_list.append(properties)
    return properties_list


DETECTED = "tb_detected"
NOT_DETECTED = "tb_not_detected"
NO_RESULT = "no_result"


def clean_result(value):
    return {
        "": NO_RESULT,
        # TODO: Confirm with Sheel that "Contaminated" should be "no result"
        "Conta": NO_RESULT,
        "CONTA": NO_RESULT,
        "NA": NO_RESULT,
        "NEG": NOT_DETECTED,
        "Negative": NOT_DETECTED,
        "pos": DETECTED,
        "Positive": DETECTED,
    }[value]


def result_label(result):
    if result == NO_RESULT:
        return "Unknown"
    elif result == DETECTED:
        return "TB Detected"
    elif result == NOT_DETECTED:
        return "TB Not Detected"
    else:
        raise Exception("Unexpected test result value")


def clean_date(messy_date_string):
    if messy_date_string:
        if isinstance(messy_date_string, datetime.date):
            return messy_date_string
        # TODO: Might be safer to assume a format and raise an exception if its in a different format
        # parse("") returns today, which we don't want.
        cleaned_datetime = parse(messy_date_string)
        return cleaned_datetime.date()


def match_district(domain, xlsx_district_name):
    """
    Given district name taken from the spreadsheet, return the name and id of the matching location in HQ.
    """
    # TODO: Consider filtering by location type
    try:
        location = SQLLocation.active_objects.get(domain=domain, name__iexact=xlsx_district_name)
    except SQLLocation.DoesNotExist:
        possible_matches = SQLLocation.active_objects.filter(domain=domain).filter(models.Q(name__icontains=xlsx_district_name))
        if len(possible_matches) == 1:
            location = possible_matches[0]
        else:
            return None, None
    return location.name, location.location_id


def match_facility(domain, xlsx_facility_name):
    """
    Given facility name taken from the spreadsheet, return the name and id of the matching location in HQ.
    """
    # TODO: Consider filtering by location type
    return match_district(domain, xlsx_facility_name)


class ColumnMapping(object):
    pass


mehsana_2016_mapping = {
    "person_name": 3,
    "district_name": 5,
    "report_sending_date": 7,
    "treatment_initiation_date": 12,
    "registration_date": 13,
    "date_put_on_mdr_treatment": 19,
    "type_of_treatment_initiated": 47,
    "mdr_selection_criteria": 4,
    "testing_facility": 1,
    "dst_result": 6,
    "month_3_follow_up_send_date": 50,
    "month_3_follow_up_result_date": 51,
    "month_3_follow_up_result": 52,
    "month_4_follow_up_send_date": 53,
    "month_4_follow_up_result_date": 54,
    "month_4_follow_up_result": 55,
    "month_6_follow_up_send_date": 56,
    "month_6_follow_up_result_date": 57,
    "month_6_follow_up_result": 58,
    "S": 28,
    "H (0.1)": 29,
    "H (0.4)": 30,
    "R": 31,
    "Z": 32,
    "Km": 33,
    "Cm": 34,
    # "Lfx": 35,
    # "Mfx (0,5)": 36,
    # "Mfx (2)": 37,
    # "PAS": 38,
    # "Lzd": 39,
}

DRUG_MAP = {
    # column key -> (id, name)
    "S": ("s", "S"),
    "H (0.1)": ("h_inha", "H (inhA)"),
    "H (0.4)": ("h_katg", "H (katG)"),
    "R": ("r", "R"),
    "Z": ("z", "Z"),
    "Km": ("km", "KM"),
    "Cm": ("cm", "CM"),
}


class Mehsana2016ColumnMapping(ColumnMapping):

    @staticmethod
    def get_value(normalized_column_name, row):
        # TODO: Confirm what this returns if cell is empty (we probably don't want None, do want "")
        column_index = mehsana_2016_mapping[normalized_column_name]
        return row[column_index].value

# TODO: Add 2017 mapping

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('excel_file_path')

    def handle(self, domain, excel_file_path, **options):

        with open_any_workbook(excel_file_path) as workbook:
            for i, row in enumerate(workbook.worksheets[0].iter_rows()):
                if i == 0:
                    import ipdb; ipdb.set_trace()
                    # Skip the headers row
                    continue
                import ipdb; ipdb.set_trace()
                case_structures = get_case_structures_from_row(domain, row)
                # TODO: submit forms with case structures
