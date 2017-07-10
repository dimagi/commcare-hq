import logging

import datetime
import uuid

from dateutil.parser import parse
from django.core.management import (
    BaseCommand,
)
from django.db import models

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from corehq.apps.locations.models import SQLLocation
from corehq.util.workbook_reading import open_any_workbook
from custom.enikshay.case_utils import CASE_TYPE_PERSON, CASE_TYPE_OCCURRENCE, CASE_TYPE_EPISODE, CASE_TYPE_TEST, \
    CASE_TYPE_DRUG_RESISTANCE, CASE_TYPE_SECONDARY_OWNER

logger = logging.getLogger('two_b_datamigration')


DETECTED = "tb_detected"
NOT_DETECTED = "tb_not_detected"
NO_RESULT = "no_result"

# Map format is: MDR selection criteria value -> (rft_drtb_diagnosis value, rft_drtb_diagnosis_ext_dst value)
# TODO: Fill in these Nones
SELECTION_CRITERIA_MAP = {
    "MDR sus -Pre.Treat At diagnosis(Smear+ve/-ve)": ("mdr_at_diagnosis", None),
    "MDR sus -Pre.Treat At diagnosis(Smear+ve/-ve).": ("mdr_at_diagnosis", None),
    "MDR sus-Private Referral": ("private_referral", None),
    "MDR sus -NSP/NSN At diagnosis": (None, None),
    "MDR sus -Follow up Sm+ve": ("follow_up_sm_ve_ip", None),
    "MDR sus -Contact of MDR/RR TB": ("contact_of_mdr_rr", None),
    "MDR sus -New At diagnosis(Smear+ve/-ve)": ("mdr_at_diagnosis", None),
    "MDR sus -Discordance Resolution": ("discordance_resolution", None),
    "EP Presumptive": (None, None),
    "PLHIV Presumptive": (None, None),
    "Pre XDR-MDR/RR TB at Diagnosis": ("extended_dst", "mdr_rr_diagnosis"),
    "Pre XDR >4 months culture positive": ("extended_dst", None),
    "Pre XDR -Failure of MDR/RR-TB regimen": ("extended_dst", "mdr_rr_failure"),
    "Pre XDR -Recurrent case of second line treatment": ("extended_dst", "recurrent_second_line_treatment"),
    "Pre XDR -Culture reversion": ("extended_dst", "culture_reversion"),
    "Paediatric Presumptive": (None, None),
    "HIV -EP TB": (None, None),
    "HIV TB (Smear+ve)": (None, None),
    "HIV TB (Smear+ve at diagnosis)": (None, None),
    "Other": (None, None),
}


# A map of column identifier to column index in the Mehsana 2016 excel sheet.
MEHSANA_2017_MAP = {
    "testing_facility": 1,
    "person_name": 3,
    "mdr_selection_criteria": 4,
    "district_name": 5,
    "report_sending_date": 6,
    "nikshay_id": 7,
    "S": 10,
    "H (0.1)": 11,
    "H (0.4)": 12,
    "R": 13,
    "E": 14,
    "Z": 15,
    "Km": 16,
    "Cm": 17,
    "Am": 18,
    "Lfx": 19,
    "Mfx (0.5)": 20,
    "Mfx (2.0)": 21,
    "PAS": 22,
    "Lzd": 23,
    "Cfz": 24,
    "Eto": 25,
    "Clr": 26,
    "Azi": 27,
    "treatment_initiation_center": 34,
    "treatment_status": 35,
    "drtb_number": 36,
    "treatment_initiation_date": 37,
    "reason_for_not_initiation_on_treatment": 41,
    "type_of_treatment_initiated": 44,
    "date_put_on_mdr_treatment": 45,
    "month_3_follow_up_send_date": 47,
    "month_3_follow_up_result_date": 48,
    "month_3_follow_up_result": 50,
    "month_4_follow_up_send_date": 51,
    "month_4_follow_up_result_date": 52,
    "month_4_follow_up_result": 54,
    "month_5_follow_up_send_date": 55,
    "month_5_follow_up_result_date": 56,
    "month_5_follow_up_result": 58,
    "month_6_follow_up_send_date": 59,
    "month_6_follow_up_result_date": 60,
    "month_6_follow_up_result": 62,
    "month_9_follow_up_send_date": 63,
    "month_9_follow_up_result_date": 64,
    "month_9_follow_up_result": 66,
    "month_12_follow_up_send_date": 67,
    "month_12_follow_up_result_date": 68,
    "month_12_follow_up_result": 70,
    "month_end_follow_up_send_date": 71,
    "month_end_follow_up_result_date": 72,
    "month_end_follow_up_result": 74,
    "treatment_outcome": 75,
    "date_of_treatment_outcome": 76,
}


# A map of column identifier to column index in the Mehsana 2017 excel sheet.
MEHSANA_2016_MAP = {
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
    "E": 32,
    "Z": 33,
    "Km": 34,
    "Cm": 35,
    "Am": 36,
    "Lfx": 37,
    "Mfx (0.5)": 38,
    "Mfx (2.0)": 39,
    "PAS": 40,
    "Lzd": 41,
    "Cfz": 42,
    "Eto": 43,
    "Clr": 44,
    "Azi": 45,
}

# A map of column identifier to column index in the Mumbai excel sheet.
MUMBAI_MAP = {
    "drtb_number": 3,
    "registration_date": 7,
    "person_name": 8,
    "sex": 9,
    "age_entered": 10,
    "address": 11,
    "phone_number": 12,
    "initial_home_visit_date": 14,
    "aadhaar_number": 15,
    "social_scheme": 16,
    "district_name": 18,
    "phi_name": 21,
    "site_of_disease": 24,  # TODO: Map this value to case properties
    "type_of_patient": 25,  # TODO: Map this value to case properties
    "weight": 26,
    "weight_band": 27,
    "height": 28,
    # TODO: Finish me
}


# A map of column identifier to the corresponding app drug id
DRUG_MAP = {
    "S": "s",
    "H (0.1)": "h_inha",
    "H (0.4)": "h_katg",
    "R": "r",
    "E": "e",
    "Z": "z",
    "Km": "km",
    "Cm": "cm",
    "Am": "am",
    "Lfx": "lfx",
    "Mfx (0.5)": "mfx_05",
    "Mfx (2.0)": "mfx_20",
    "PAS": "pas",
    "Lzd": "lzd",
    "Cfz": "cfz",
    "Eto": "eto",
    "Clr": "clr",
    "Azi": "azi",
}


ALL_MAPPING_DICTS = (MEHSANA_2016_MAP, MEHSANA_2017_MAP, MUMBAI_MAP)


class ColumnMapping(object):
    mapping_dict = None

    @classmethod
    def get_value(cls, normalized_column_name, row):
        try:
            column_index = cls.mapping_dict[normalized_column_name]
            return row[column_index].value
        except KeyError:
            return cls.handle_mapping_miss(normalized_column_name)
        except IndexError:
            return None

    @classmethod
    def handle_mapping_miss(cls, normalized_column_name):
        exists_in_some_mapping = False
        for mapping in ALL_MAPPING_DICTS:
            if normalized_column_name in mapping:
                exists_in_some_mapping = True
                break
        if exists_in_some_mapping:
            return None
        else:
            raise KeyError("Invalid normalized_column_name passed to ColumnMapping.get_value()")


class Mehsana2017ColumnMapping(ColumnMapping):
    mapping_dict = MEHSANA_2017_MAP


class Mehsana2016ColumnMapping(ColumnMapping):
    mapping_dict = MEHSANA_2016_MAP


class MumbaiColumnMapping(ColumnMapping):
    mapping_dict = MUMBAI_MAP


class MumbaiConstants(object):
    """A collection of Mumbai specific constants"""
    # TODO: (WAITING) find out these values
    drtb_center_name = None
    drtb_center_id = None


class MehsanaConstants(object):
    """A collection of Mehsana specific constants"""
    drtb_center_name = "Patan - DRTB-HIV"
    drtb_center_id = "becf3acefc51b425b553a66f3dbf387c"


def get_case_structures_from_row(domain, migration_id, column_mapping, city_constants, row):
    person_case_properties = get_person_case_properties(domain, column_mapping, row)
    occurrence_case_properties = get_occurrence_case_properties(column_mapping, row)
    episode_case_properties = get_episode_case_properties(domain, column_mapping, row)
    test_case_properties = get_test_case_properties(domain, column_mapping, row)
    drug_resistance_case_properties = get_drug_resistance_case_properties(column_mapping, row)
    followup_test_cases_properties = get_follow_up_test_case_properties(
        column_mapping, row, episode_case_properties['treatment_initiation_date'])
    secondary_owner_case_properties = get_secondary_owner_case_properties(city_constants)

    person_case_structure = get_case_structure(CASE_TYPE_PERSON, person_case_properties, migration_id)
    occurrence_case_structure = get_case_structure(
        CASE_TYPE_OCCURRENCE, occurrence_case_properties, migration_id, host=person_case_structure)
    episode_case_structure = get_case_structure(
        CASE_TYPE_EPISODE, episode_case_properties, migration_id, host=occurrence_case_structure)
    test_case_structure = get_case_structure(
        CASE_TYPE_TEST, test_case_properties, migration_id, host=occurrence_case_structure)
    drug_resistance_case_structures = [
        get_case_structure(CASE_TYPE_DRUG_RESISTANCE, props, migration_id, host=occurrence_case_structure)
        for props in drug_resistance_case_properties
    ]
    followup_test_case_structures = [
        get_case_structure(CASE_TYPE_TEST, props, migration_id, host=occurrence_case_structure)
        for props in followup_test_cases_properties
    ]
    secondary_owner_case_structure = get_case_structure(
        CASE_TYPE_SECONDARY_OWNER, secondary_owner_case_properties, migration_id, host=occurrence_case_structure)

    return [
        person_case_structure,
        occurrence_case_structure,
        episode_case_structure,
        test_case_structure,
        secondary_owner_case_structure
    ] + drug_resistance_case_structures + followup_test_case_structures


def get_case_structure(case_type, properties, migration_identifier, host=None):
    owner_id = properties.pop("owner_id")
    props = {k: v for k, v in properties.iteritems() if v is not None}
    props['__created_by_migration'] = migration_identifier
    kwargs = {
        "case_id": uuid.uuid4().hex,
        "walk_related": False,
        "attrs": {
            "case_type": case_type,
            "create": True,
            "owner_id": owner_id,
            "update": props,
        },
    }
    if host:
        kwargs['indices'] = [CaseIndex(
            host,
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type=host.attrs['case_type'],
        )],
    return CaseStructure(**kwargs)


def get_person_case_properties(domain, column_mapping, row):
    person_name = column_mapping.get_value("person_name", row)
    xlsx_district_name = column_mapping.get_value("district_name", row)
    district_name, district_id = match_district(domain, xlsx_district_name)
    phi_name, phi_id = match_phi(domain, column_mapping.get_value("phi_name", row))
    tu_name, tu_id = get_tu(domain, phi_id)

    properties = {
        "name": person_name,
        "district_name": district_name,
        "district_id": district_id,
        "owner_id": phi_id or "-",
        "current_episode_type": "confirmed_drtb",
        "nikshay_id": column_mapping.get_value("nikshay_id", row),
        "sex": column_mapping.get_value("sex", row),
        "age_entered": column_mapping.get_value("age_entered", row),
        "current_address": column_mapping.get_value("address", row),
        "phone_number": column_mapping.get_value("phone_number", row),  # TODO: Review Gio's email about SMS
        "aadhaar_number": column_mapping.get_value("aadhaar_number", row),
        "phi_name": phi_name,
        "tu_name": tu_name,
        "tu_id": tu_id,
        # site_of_disease TODO
    }

    social_scheme = column_mapping.get_value("social_scheme", row)
    if social_scheme:
        raise Exception("has social scheme: {}".format(social_scheme))

    return properties


def get_occurrence_case_properties(column_mapping, row):
    return {
        "owner_id": "-",
        "current_episode_type": "confirmed_drtb",
        "initial_home_visit_status":
            "completed" if column_mapping.get_value("initial_home_visit_date", row) else None,
    }


def get_episode_case_properties(domain, column_mapping, row):

    report_sending_date = column_mapping.get_value("report_sending_date", row)
    report_sending_date = clean_date(report_sending_date)

    treatment_initiation_date = column_mapping.get_value("treatment_initiation_date", row)
    treatment_initiation_date = clean_date(treatment_initiation_date)

    treatment_card_completed_date = column_mapping.get_value("registration_date", row)
    treatment_card_completed_date = clean_date(treatment_card_completed_date)
    if not treatment_card_completed_date:
        treatment_card_completed_date = treatment_initiation_date

    properties = {
        "owner_id": "-",
        "episode_type": "confirmed_drtb",
        "episode_pending_registration": "no",
        "is_active": "yes",
        "date_of_diagnosis": report_sending_date,
        "diagnosis_test_result_date": report_sending_date,
        "treatment_initiation_date": treatment_initiation_date,
        "treatment_card_completed_date": treatment_card_completed_date,
        "regimen_change_history": get_episode_regimen_change_history(
            column_mapping, row, treatment_initiation_date),
        "treatment_initiating_facility_id": match_facility(
            domain, column_mapping.get_value("treatment_initiation_center", row)
        )[1],
        "pmdt_tb_number": column_mapping.get_value("drtb_number", row),
        "treatment_status_other": column_mapping.get_value("reason_for_not_initiation_on_treatment", row),
        "treatment_outcome": convert_treatment_outcome(column_mapping.get_value("treatment_outcome", row)),
        "treatment_outcome_date": clean_date(column_mapping.get_value("date_of_treatment_outcome", row)),
        "weight": column_mapping.get_value("weight", row),
        "weight_band": clean_weight_band(column_mapping.get_value("weight_band", row)),
        "height": column_mapping.get_value("height", row),  # TODO: Do I need to clean this?
    }

    raw_treatment_status = column_mapping.get_value("treatment_status", row)
    if raw_treatment_status:
        treatment_status_id = convert_treatment_status(raw_treatment_status)
        properties["treatment_status"] = treatment_status_id
        if treatment_status_id not in ("other", "", None):
            properties["treatment_initiated"] = "yes_phi"

    properties.update(get_selection_criteria_properties(column_mapping, row))
    if treatment_initiation_date:
        properties["treatment_initiated"] = "yes_phi"

    return properties


def convert_disease_site(xlsx_value):
    if xlsx_value.split()[0] in ("EP", "Extrapulmonary"):
        return "extra_pulmonary"
    # TODO: Finish me
    # TODO: Ask sheel about what other stuff means
    # What to do about "P EP" "P EP R Effusion"


def convert_treatment_outcome(xlsx_value):
    return {
        "DIED": "died",
        None: None
    }[xlsx_value]


def get_selection_criteria_properties(column_mapping, row):
    selection_criteria_value = column_mapping.get_value("mdr_selection_criteria", row)
    if not selection_criteria_value:
        return {}
    rft_drtb_diagnosis, rft_drtb_diagnosis_ext_dst = SELECTION_CRITERIA_MAP[selection_criteria_value]

    properties = {
        "rft_general": "drtb_diagnosis",
    }
    if rft_drtb_diagnosis:
        properties["rft_drtb_diagnosis"] = rft_drtb_diagnosis
    if rft_drtb_diagnosis_ext_dst:
        properties["rft_drtb_diagnosis_ext_dst"] = rft_drtb_diagnosis_ext_dst
    return properties


def get_resistance_properties(column_mapping, row):
    property_map = {
        "Rif-Resi": ("r", "R: Res"),
        "Rif Resi+Levo Resi": ("r lfx", "R: Res\nLFX: Res"),
        "Rif Resi+Levo Resi+K Resi": ("r lfx km", "R: Res\nLFX: Res\nKM: Res"),
        "Rif Resi+K Resi": ("r km", "R: Res\nKM: Res"),
    }
    dst_result_value = column_mapping.get_value("dst_result", row)
    if dst_result_value:
        return {
            "drug_resistance_list": property_map[dst_result_value][0],
            "result_summary_display": property_map[dst_result_value][1]
        }
    else:
        return {}


def get_episode_regimen_change_history(column_mapping, row, episode_treatment_initiation_date):
    put_on_treatment = column_mapping.get_value("date_put_on_mdr_treatment", row)
    put_on_treatment = clean_date(put_on_treatment)
    value = "{}: MDR/RR".format(episode_treatment_initiation_date)
    if put_on_treatment:
        value += "\n{}: {}".format(
            put_on_treatment,
            column_mapping.get_value("type_of_treatment_initiated", row)
        )
    return value


def get_test_case_properties(domain, column_mapping, row):
    facility_name, facility_id = match_facility(
        domain, column_mapping.get_value("testing_facility", row))
    properties = {
        "owner_id": "-",
        "testing_facility_saved_name": facility_name,
        "testing_facility_id": facility_id,
        "date_reported": column_mapping.get_value("report_sending_date", row),
    }
    properties.update(get_selection_criteria_properties(column_mapping, row))
    properties.update(get_resistance_properties(column_mapping, row))
    return properties


def get_drug_resistance_case_properties(column_mapping, row):
    resistant_drugs = {
        d['drug_id']: d
        for d in get_drug_resistances_from_drug_resistance_list(column_mapping, row)
    }
    additional_drug_case_properties = get_drug_resistances_from_individual_drug_columns(column_mapping, row)
    for drug in additional_drug_case_properties:
        resistant_drugs[drug['drug_id']] = drug
    return resistant_drugs.values()


def get_drug_resistances_from_individual_drug_columns(column_mapping, row):
    case_properties = []
    for drug_column_key, drug_id in DRUG_MAP.iteritems():
        value = column_mapping.get_value(drug_column_key, row)
        properties = {
            "name": drug_id,
            "owner_id": "-",
            "sensitivity": convert_sensitivity(value),
            "drug_id": drug_id,
        }
        case_properties.append(properties)
    return case_properties


def convert_sensitivity(sensitivity_value):
    return {
        "S": "sensitive",
        "R": "resistant",
        "Conta": "unknown",
        "": "unknown",
        "Neg": "unknown",  # TODO: Which should this be?
        None: "unknown",
    }[sensitivity_value]


def convert_treatment_status(status_in_xlsx):
    second_line = "initiated_on_second_line_treatment"
    first_line = "initiated_first_line_treatment"
    return {
        "Mono H": first_line,
        "CAT I/II": first_line,
        "Cat IV": second_line,
        "Cat-iv": second_line,
        "Cat iv": second_line,
        "CAT IV": second_line,
        "CAT-IV": second_line,
        "CATIV": second_line,
        "Cat V": second_line,
        "Not initiated (reason remark)": "other",
    }[status_in_xlsx]


def get_drug_resistances_from_drug_resistance_list(column_mapping, row):
    drugs = get_resistance_properties(column_mapping, row).get("drug_resistance_list", "").split(" ")
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


def get_follow_up_test_case_properties(column_mapping, row, treatment_initiation_date):
    properties_list = []
    for follow_up in (3, 4, 5, 6, 9, 12, "end"):
        if column_mapping.get_value("month_{}_follow_up_send_date".format(follow_up), row):
            properties = {
                "owner_id": "-",
                "date_tested": clean_date(
                    column_mapping.get_value("month_{}_follow_up_send_date".format(follow_up), row)),
                "date_reported": clean_date(
                    column_mapping.get_value("month_{}_follow_up_result_date".format(follow_up), row)),
                "result": clean_result(
                    column_mapping.get_value("month_{}_follow_up_result".format(follow_up), row)),
                "test_type_value": "culture",
                "test_type_label": "culture",
                "rft_general": "follow_up_drtb",
            }
            properties["rft_drtb_follow_up_treatment_month"] = get_follow_up_month(
                follow_up, properties['date_tested'], treatment_initiation_date
            )
            properties["result_summary_label"] = result_label(properties['result'])

            properties_list.append(properties)
    return properties_list


def get_follow_up_month(follow_up_month_identifier, date_tested, treatment_initiation_date):
    if isinstance(follow_up_month_identifier, int):
        return str(follow_up_month_identifier)
    else:
        return str(int(round((date_tested - treatment_initiation_date).days / 30.4)))


def get_secondary_owner_case_properties(city_constants):
    return {
        "secondary_owner_name": city_constants.drtb_center_name,
        "secondary_owner_type": "DRTB",
        "owner_id": city_constants.drtb_center_id,
    }

def clean_weight_band(value):
    pass
    # TODO: Finish me


def clean_hiv_status(value):
    NON_REACTIVE = "non_reactive"
    REACTIVE = "reactive"
    if not value:
        return None
    if value.startswith("Non Reactive") or value.startswith("NR") or value.startswith("Nr"):
        return NON_REACTIVE
    if value.startswith("R ") or value.startswith("Reactive") or value.startswith("Ractive"):
        return REACTIVE
    return {
        "Pos": REACTIVE,  #? TODO
        "Positive": REACTIVE,  #? TODO
    }[value]


def clean_result(value):
    return {
        None: NO_RESULT,
        "conta": NO_RESULT,
        "Conta": NO_RESULT,
        "CONTA": NO_RESULT,
        "NA": NO_RESULT,
        "Neg": NO_RESULT,
        "NEG": NOT_DETECTED,
        "Negative": NOT_DETECTED,
        "negative": NOT_DETECTED,
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
    # TODO: Consider filtering by location type
    return match_location(domain, xlsx_district_name)


def match_location(domain, xlsx_name, location_type=None):
    """
    Given location name taken from the spreadsheet, return the name and id of the matching location in HQ.
    """
    if not xlsx_name:
        return None, None
    try:
        kwargs = {"domain": domain, "name__iexact": xlsx_name}
        if location_type:
            kwargs["location_type__code"] = location_type
        location = SQLLocation.active_objects.get(**kwargs)
    except SQLLocation.DoesNotExist:
        kwargs = {"domain": domain}
        if location_type:
            kwargs["location_type__code"] = location_type
        possible_matches = SQLLocation.active_objects.filter(**kwargs).filter(models.Q(name__icontains=xlsx_name))
        if len(possible_matches) == 1:
            location = possible_matches[0]
        elif len(possible_matches) > 1:
            raise Exception("Multiple location matches for {}".format(xlsx_name))
        else:
            raise Exception("No location matches for {}".format(xlsx_name))
    return location.name, location.location_id


def match_facility(domain, xlsx_facility_name):
    """
    Given facility name taken from the spreadsheet, return the name and id of the matching location in HQ.
    """
    # TODO: Consider filtering by location type
    return match_location(domain, xlsx_facility_name)


def match_phi(domain, xlsx_phi_name):
    return match_location(domain, xlsx_phi_name, "phi")


def get_tu(domain, phi_id):
    if not phi_id:
        return None, None
    phi = SQLLocation.get(domain=domain, location_id=phi_id)
    return phi.parent.name, phi.parent.location_id


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="the domain to create the new cases in"
        )
        parser.add_argument(
            'excel_file_path',
            help="a path to an excel file to be imported"
        )
        parser.add_argument(
            'format',
            help="the format of the given excel file. Options are mehsana2016, mehsana2017, or mumbai",
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually create the cases. Without this flag, it's a dry run."
        )

    def handle(self, domain, excel_file_path, format, **options):

        migration_id = str(datetime.datetime.now())
        self.log_meta_info(migration_id, options['commit'])
        column_mapping = self.get_column_mapping(format)
        city_constants = self.get_city_constants(format)
        case_factory = CaseFactory(domain)

        with open_any_workbook(excel_file_path) as workbook:
            for i, row in enumerate(workbook.worksheets[0].iter_rows()):
                if i == 0:
                    # Skip the headers row
                    continue
                try:
                    case_structures = get_case_structures_from_row(
                        domain, migration_id, column_mapping, city_constants, row
                    )
                    logger.info("Creating cases for row {}. Case ids are: {}".format(
                        i, ", ".join([x.case_id for x in case_structures])
                    ))
                    if options['commit']:
                        case_factory.create_or_update_cases(case_structures)
                except Exception as e:
                    logger.info("Creating case structures for row {} failed".format(i))
                    raise e

    @staticmethod
    def log_meta_info(migration_id, commit):
        logger.info("Starting DRTB import with id {}".format(migration_id))
        if commit:
            logger.info("This is a REAL RUN")
        else:
            logger.info("This is a dry run")

    @staticmethod
    def get_column_mapping(format):
        if format == "mehsana2016":
            return Mehsana2016ColumnMapping
        elif format == "mehsana2017":
            return Mehsana2017ColumnMapping
        elif format == "mumbai":
            return MumbaiColumnMapping
        else:
            raise Exception("Invalid format. Format must be mehsana2016, mehsana2017, or mumbai")

    @staticmethod
    def get_city_constants(format):
        # TODO: Use constants for formats
        if format in ("mehsana2016", "mehsana2017"):
            return MehsanaConstants
        elif format == "mumbai":
            return MumbaiColumnMapping
        else:
            raise Exception("Invalid format. Format must be mehsana2016, mehsana2017, or mumbai")

