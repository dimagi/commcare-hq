import logging

import datetime
import uuid

import re
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
# TODO: (WAITING) Fill in these Nones
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
    "nikshay_id": 5,
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
    "reason_for_testing": 23,
    "site_of_disease": 24,
    "type_of_patient": 25,  # TODO: (WAITING) Map this value to case properties
    "weight": 26,
    "weight_band": 27,
    "height": 28,
    "hiv_status": 29,
    "hiv_test_date": 30,
    "hiv_program_id": 31,
    "cpt_initiation_date": 32,
    "art_initiation_date": 33,
    "diabetes": 34,
    "cbnaat_lab": 35,  # This is similar to testing_facility, but slightly different
    "cbnaat_sample_date": 36,
    "cbnaat_result": 37,
    "cbnaat_result_date": 38,
    "lpa_lab": 39,
    "lpa_sample_date": 40,
    "lpa_rif_result": 41,
    "lpa_inh_result": 42,
    "lpa_result_date": 43,
    "sl_lpa_lab": 44,
    "sl_lpa_sample_date": 45,
    "sl_lpa_result": 46,
    "sl_lpa_result_date": 47,
    "culture_lab": 48,
    "culture_sample_date": 49,
    "culture_type": 50,
    "culture_result": 51,
    "culture_result_date": 52,
    "dst_sample_date": 53,
    "dst_type": 54,
    # TODO: (WAITING) DST Drug specific columns
    # TODO: (WAITING) not sure how this maps
    "bdq_eligible": 70,
    "treatment_initiation_date": 71,
    "treatment_initiated_by": 72,
    "drtb_type": 74,
    # TODO: (WAITING) treatment status here is different sorts of values than in the other mappings
    # "treatment_status": 75,
    "ip_to_cp_date": 79,
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

# This is a copy of part of the "resistance_drug" fixture
ALL_DRUGS = {
    "r": "01",
    "h_inha": "02",
    "h_katg": "03",
    "s": "04",
    "e": "05",
    "z": "06",
    "slid_class": "07",
    "km": "08",
    "cm": "09",
    "am": "10",
    "fq_class": "11",
    "lfx": "12",
    "mfx_05": "14",
    "mfx_20": "15",
    "eto": "16",
    "pas": "17",
    "lzd": "18",
    "cfz": "19",
    "clr": "20",
    "azi": "21",
    "bdq": "22",
    "dlm": "23",
}

ALL_MAPPING_DICTS = (MEHSANA_2016_MAP, MEHSANA_2017_MAP, MUMBAI_MAP)


class ColumnMapping(object):
    mapping_dict = None
    required_fields = []

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
            raise KeyError(
                "Invalid normalized_column_name '{}' passed to ColumnMapping.get_value()".format(
                    normalized_column_name
                )
            )

    @classmethod
    def check_for_required_fields(cls, row):
        """Raise an exception if row is missing a required field"""
        for key in cls.required_fields:
            val = cls.get_value(key, row)
            if not val:
                raise Exception("{} is required".format(key))


class Mehsana2017ColumnMapping(ColumnMapping):
    mapping_dict = MEHSANA_2017_MAP
    required_fields = (
        "person_name",
        "district_name",
    )


class Mehsana2016ColumnMapping(ColumnMapping):
    mapping_dict = MEHSANA_2016_MAP
    required_fields = (
        "person_name",
        "district_name",
    )


class MumbaiColumnMapping(ColumnMapping):
    mapping_dict = MUMBAI_MAP
    required_fields = (
        "registration_date",
        "person_name",
        "district_name",
        "phi_name",
        # The phi must also be valid, but this is checked in the match_phi function.
    )
    follow_up_culture_index_start = 90
    follow_up_culture_month_start = 3

    @classmethod
    def get_follow_up_culture_result(cls, month, row):
        if month == 36:
            # For some reason the sheet jumps from 33 to 36, so just special casing it.
            index = 152
        else:
            assert month >= 3 and month <= 33
            offset = (month - 3) * 2
            index = cls.follow_up_culture_index_start + offset
        try:
            return row[index].value
        except IndexError:
            return None

    @classmethod
    def get_follow_up_culture_date(cls, month, row):
        if month == 36:
            # For some reason the sheet jumps from 33 to 36, so just special casing it.
            index = 153
        else:
            assert month >= 3 and month <= 33
            offset = ((month - 3) * 2) + 1
            index = cls.follow_up_culture_index_start + offset
        try:
            return row[index].value
        except IndexError:
            return None


class MumbaiConstants(object):
    """A collection of Mumbai specific constants"""
    # TODO: (WAITING) Fill in these values
    # This is waiting on upload of the locations. It looks like for mumbai these might not be constants
    drtb_center_name = None
    drtb_center_id = None


class MehsanaConstants(object):
    """A collection of Mehsana specific constants"""
    # TODO: (WAITING) Fill in these values
    # This is waiting on upload of the locations
    drtb_center_name = None
    drtb_center_id = None


def get_case_structures_from_row(domain, migration_id, column_mapping, city_constants, row):
    person_case_properties = get_person_case_properties(domain, column_mapping, row)
    occurrence_case_properties = get_occurrence_case_properties(column_mapping, row)
    episode_case_properties = get_episode_case_properties(domain, column_mapping, row)
    test_case_properties = get_test_case_properties(
        domain, column_mapping, row, episode_case_properties['treatment_initiation_date'])
    drug_resistance_case_properties = get_drug_resistance_case_properties(column_mapping, row)
    secondary_owner_case_properties = get_secondary_owner_case_properties(city_constants)

    person_case_structure = get_case_structure(CASE_TYPE_PERSON, person_case_properties, migration_id)
    occurrence_case_structure = get_case_structure(
        CASE_TYPE_OCCURRENCE, occurrence_case_properties, migration_id, host=person_case_structure)
    episode_case_structure = get_case_structure(
        CASE_TYPE_EPISODE, episode_case_properties, migration_id, host=occurrence_case_structure)
    drug_resistance_case_structures = [
        get_case_structure(CASE_TYPE_DRUG_RESISTANCE, props, migration_id, host=occurrence_case_structure)
        for props in drug_resistance_case_properties
    ]
    test_case_structures = [
        get_case_structure(CASE_TYPE_TEST, props, migration_id, host=occurrence_case_structure)
        for props in test_case_properties
    ]
    secondary_owner_case_structure = get_case_structure(
        CASE_TYPE_SECONDARY_OWNER, secondary_owner_case_properties, migration_id, host=occurrence_case_structure)

    return [
        person_case_structure,
        occurrence_case_structure,
        episode_case_structure,
        secondary_owner_case_structure
    ] + drug_resistance_case_structures + test_case_structures


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
        "dto_name": district_name,
        "dto_id": district_id,
        "owner_id": phi_id or "-",
        "current_episode_type": "confirmed_drtb",
        "nikshay_id": column_mapping.get_value("nikshay_id", row),
        "sex": column_mapping.get_value("sex", row),
        "age_entered": column_mapping.get_value("age_entered", row),
        "current_address": column_mapping.get_value("address", row),
        "aadhaar_number": column_mapping.get_value("aadhaar_number", row),
        "phi_name": phi_name,
        "tu_name": tu_name,
        "tu_id": tu_id,
        "hiv_status": clean_hiv_status(column_mapping.get_value("hiv_status", row)),
        "hiv_test_date": clean_date(column_mapping.get_value("hiv_test_date", row)),
        "hiv_program_id": column_mapping.get_value("hiv_program_id", row),
        "cpt_initiation_date": clean_date(column_mapping.get_value("cpt_initiation_date", row)),
        "art_initiation_date": clean_date(column_mapping.get_value("art_initiation_date", row)),
        "diabetes_status": clean_diabetes_status(column_mapping.get_value("diabetes", row))
    }

    properties.update(get_disease_site_properties_for_person(column_mapping, row))

    if properties["cpt_initiation_date"]:
        properties["cpt_initiated"] = "yes"
    if properties["art_initiation_date"]:
        properties["art_initiated"] = "yes"

    phone_number = column_mapping.get_value("phone_number", row)
    if phone_number:
        properties['contact_phone_number'] = clean_phone_number(phone_number, 12)
        properties['phone_number'] = clean_phone_number(phone_number, 10)
        properties['language_code'] = "hin"

    social_scheme = column_mapping.get_value("social_scheme", row)
    if social_scheme:
        raise Exception("has social scheme: {}".format(social_scheme))

    return properties


def get_occurrence_case_properties(column_mapping, row):
    properties = {
        "owner_id": "-",
        "current_episode_type": "confirmed_drtb",
        "initial_home_visit_status":
            "completed" if column_mapping.get_value("initial_home_visit_date", row) else None,
        "drtb_type": clean_drtb_type(column_mapping.get_value("drtb_type", row)),

        'name': 'Occurrence #1',
        'occurrence_episode_count': 1,
    }
    properties.update(get_disease_site_properties(column_mapping, row))

    return properties


def get_episode_case_properties(domain, column_mapping, row):

    if column_mapping.get_value("treatment_initiated_by", row):
        raise NotImplementedError(
            "No example data was in the original data dump, so didn't know how to handle it.")

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
        "height": clean_height(column_mapping.get_value("height", row)),
        "diagnosis_test_specimen_date": clean_date(column_mapping.get_value("cbnaat_sample_date", row))
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

    properties.update(get_diagnosis_properties(column_mapping, domain, row))

    properties.update(get_reason_for_test_properties(column_mapping, row))

    ip_to_cp_date = clean_date(column_mapping.get_value("ip_to_cp_date", row))
    if ip_to_cp_date:
        properties.update({
            "cp_initiated": "yes",
            "cp_initiation_date": ip_to_cp_date,
        })

    return properties


def get_reason_for_test_properties(column_mapping, row):
    test_reason_map = {
        # TODO: there is yellow in the mapping sheet. Was sheel waiting on these?
        # https://docs.google.com/spreadsheets/d/1Pz-cYNvo5BkF-Sta1ol4ZzfBYIQ4kGlZ3FdJgBLe5WE/edit#gid=704385575
        "1-Failure": (None, "extended_dst", "mdr_rr_failure"),
        "1. Presumptive TB	diagnosis_dstb": ("presumptive_tb", None, None),
        "2-Re-treatment case S+at 4th month": (None, "extended_dst", "4mo_culture_positive"),
        "3-Contact of known MDR TB case": (None, None, None),
        "4-S+ at diagnosis, re-treatment case": (None, None, None),
        "4. Presumptive MDRTB, at diagnosis": (None, "mdr_at_diagnosis", None),
        "5-Any Follow-up S+": (None, None, None),
        "5. Contact of MDR/RR TB": (None, "contact_of_mdr_rr", None),
        "6-S-at Diagnosis re-treatment case": (None, None, None),
        "6. Follow up Sm+ve at end IP": (None, "follow_up_sm_ve_ip", None),
        "7-HIV TB Case": (None, None, None),
        "7. Private Referral-Presumptive MDRTB": (None, "private_referral", None),
        "8. Discordance resolution": (None, "discordance_resolution", None),
        "10. MDR/RR TB at diagnosis": (None, "extended_dst", "mdr_rr_diagnosis"),
        "13. Culture reversion": (None, "extended_dst", "culture_reversion"),
        "14. Failure of MDR/RR TB regimen": (None, "extended_dst", "mdr_rr_failure"),
        "15. Recurrent case of second line treatment": (None, "extended_dst", "recurrent_second_line_treatment"),
        "Private": (None, None, None),
    }
    value = column_mapping.get_value("reason_for_testing", row)
    if not value:
        return {}
    if value not in test_reason_map:
        raise Exception("Unexpected test reason: {}".format(value))
    rft_dstb_diagnosis, rft_drtb_diagnosis, rft_drtb_diagnosis_ext_dst = test_reason_map[value]
    return {
        "rft_general": "diagnosis_drtb",
        "rft_dstb_diagnosis": rft_dstb_diagnosis,
        "rft_drtb_diagnosis": rft_drtb_diagnosis,
        "rft_drtb_diagnosis_ext_dst": rft_drtb_diagnosis_ext_dst,
    }


def get_diagnosis_properties(column_mapping, domain, row):
    has_cbnaat_result = bool(column_mapping.get_value("cbnaat_result", row))
    if has_cbnaat_result:
        properties = {}
        cbnaat_lab_name, cbnaat_lab_id = match_location(domain, column_mapping.get_value("cbnaat_lab", row))
        if cbnaat_lab_name:
            properties.update({
                "diagnosing_facility_name": cbnaat_lab_name,
                "diagnosing_facility_id": cbnaat_lab_id,
                "diagnosis_test_type_label": "CBNAAT",
                "diagnosis_test_type_value": "cbnaat",
            })
        if get_cbnaat_resistance(column_mapping, row):
            properties["diagnosis_test_drug_resistance_list"] = "r"

        cbnaat_result_date = column_mapping.get_value("cbnaat_result_date", row)
        if cbnaat_result_date:
            properties.update({
                "diagnosis_test_result_date": clean_date(cbnaat_result_date),
                "date_of_diagnosis": clean_date(cbnaat_result_date),
            })
        return properties
    else:
        # TODO: (WAITING) figure out how to set these properties based on other info
        return {}


def get_disease_site_properties(column_mapping, row):
    xlsx_value = column_mapping.get_value("site_of_disease", row)
    if not xlsx_value:
        return {}
    if xlsx_value.split()[0] in ("EP", "Extrapulmonary"):
        return {"disease_classification": "extra_pulmonary"}
    # TODO: (WAITING) Best guess at mapping is here:
    # https://docs.google.com/spreadsheets/d/1Pz-cYNvo5BkF-Sta1ol4ZzfBYIQ4kGlZ3FdJgBLe5WE/edit#gid=1748484835


def get_disease_site_properties_for_person(column_mapping, row):
    props = get_disease_site_properties(column_mapping, row)
    return {"current_{}".format(k): v for k, v in props.iteritems()}


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


def get_cbnaat_test_resistance_properties(column_mapping, row):
    resistant = get_cbnaat_resistance(column_mapping, row)
    if resistant:
        return {"drug_resistance_list": "r"}
    elif (resistant is not None) and (not resistant):
        return {"drug_sensitive_list": "r"}
    else:
        return {}


def get_lpa_test_resistance_properties(column_mapping, row):
    drug_resistances = [
        ("r", clean_mumbai_test_resistance_value(column_mapping.get_value("lpa_rif_result", row))),
        ("h_inha", clean_mumbai_test_resistance_value(column_mapping.get_value("lpa_inh_result", row))),
    ]
    return {
        "drug_sensitive_list": " ".join(
            [drug for drug, resistant in drug_resistances if (not resistant) and (resistant is not None)]),
        "drug_resistance_list": " ".join([drug for drug, resistant in drug_resistances if resistant])
    }


def lpa_detected_tb(column_mapping, row):
    rif = clean_mumbai_test_resistance_value(column_mapping.get_value("lpa_rif_result", row))
    inha = clean_mumbai_test_resistance_value(column_mapping.get_value("lpa_inh_result", row))
    return (rif is not None) or (inha is not None)


def get_sl_lpa_test_resistance_properties(column_mapping, row):
    result = column_mapping.get_value("sl_lpa_result", row)
    if result is None:
        return {}
    else:
        raise NotImplementedError(
            "No example data was in the original data dump, so didn't know how to handle it.")


def get_cbnaat_resistance(column_mapping, row):
    result = column_mapping.get_value("cbnaat_result", row)
    return clean_mumbai_test_resistance_value(result)


def clean_mumbai_test_resistance_value(value):
    if value is None:
        return None
    if value.startswith("R ") or value in ("R", "R\n R", "RR"):
        resistant = True
    elif value == "S":
        resistant = False
    else:
        raise Exception("Unrecognized result: {}".format(value))
    return resistant


def get_mehsana_resistance_properties(column_mapping, row):
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


def get_test_case_properties(domain, column_mapping, row, treatment_initiation_date):
    test_cases = []

    if column_mapping.get_value("cbnaat_lab", row) or column_mapping.get_value("cbnaat_result", row):
        test_cases.append(get_cbnaat_test_case_properties(domain, column_mapping, row))
    elif column_mapping.get_value("testing_facility", row):
        test_cases.append(get_mehsana_test_case_properties(domain, column_mapping, row))

    if column_mapping.get_value("lpa_rif_result", row) or column_mapping.get_value("lpa_inh_result", row):
        test_cases.append(get_lpa_test_case_properties(domain, column_mapping, row))
    if column_mapping.get_value("sl_lpa_result", row):
        test_cases.append(get_sl_lpa_test_case_properties(domain, column_mapping, row))
    if column_mapping.get_value("culture_result", row):
        test_cases.append(get_culture_test_case_properties(domain, column_mapping, row))
    dst_test_case_properties = get_dst_test_case_properties(column_mapping, row)
    if dst_test_case_properties:
        test_cases.append(dst_test_case_properties)

    test_cases.extend(get_follow_up_test_case_properties(column_mapping, row, treatment_initiation_date))
    return test_cases


def get_mehsana_test_case_properties(domain, column_mapping, row):
    facility_name, facility_id = match_facility(domain, column_mapping.get_value("testing_facility", row))
    properties = {
        "owner_id": "-",
        "date_reported": column_mapping.get_value("report_sending_date", row),
        "testing_facility_saved_name": facility_name,
        "testing_facility_id": facility_id,
    }
    properties.update(get_selection_criteria_properties(column_mapping, row))
    properties.update(get_mehsana_resistance_properties(column_mapping, row))
    return properties


def get_cbnaat_test_case_properties(domain, column_mapping, row):
    cbnaat_lab_name, cbnaat_lab_id = match_location(domain, column_mapping.get_value("cbnaat_lab", row))

    properties = {
        "owner_id": "-",
        "date_reported": column_mapping.get_value("cbnaat_result_date", row),
        "testing_facility_saved_name": cbnaat_lab_name,
        "testing_facility_id": cbnaat_lab_id,
        "test_type_label": "CBNAAT",
        "test_type_value": "cbnaat",
        "date_tested": clean_date(column_mapping.get_value("cbnaat_sample_date", row)),
    }

    properties.update(get_cbnaat_test_resistance_properties(column_mapping, row))
    if get_cbnaat_resistance(column_mapping, row) is not None:
        properties['result'] = "tb_detected"
    return properties


def get_lpa_test_case_properties(domain, column_mapping, row):
    lpa_lab_name, lpa_lab_id = match_location(domain, column_mapping.get_value("lpa_lab", row))
    properties = {
        "owner_id": "-",
        "testing_facility_saved_name": lpa_lab_name,
        "testing_facility_id": lpa_lab_id,
        "test_type_label": "FL LPA",
        "test_type_value": "fl_line_probe_assay",
        "date_tested": clean_date(column_mapping.get_value("lpa_sample_date", row)),
        "date_reported": clean_date(column_mapping.get_value("lpa_result_date", row)),
    }

    properties.update(get_lpa_test_resistance_properties(column_mapping, row))
    if lpa_detected_tb(column_mapping, row):
        properties['result'] = "tb_detected"
    return properties


def get_sl_lpa_test_case_properties(domain, column_mapping, row):
    sl_lpa_lab_name, sl_lpa_lab_id = match_location(domain, column_mapping.get_value("sl_lpa_lab", row))
    properties = {
        "owner_id": "-",
        "testing_facility_saved_name": sl_lpa_lab_name,
        "testing_facility_id": sl_lpa_lab_id,
        "test_type_label": "SL LPA",
        "test_type_value": "sl_line_probe_assay",
        "date_tested": clean_date(column_mapping.get_value("lpa_sample_date", row)),
        "date_reported": clean_date(column_mapping.get_value("lpa_result_date", row)),
        # TODO: Should this have a "result"?
    }

    properties.update(get_sl_lpa_test_resistance_properties(column_mapping, row))
    return properties


def get_culture_test_case_properties(domain, column_mapping, row):
    lab_name, lab_id = match_location(domain, column_mapping.get_value("culture_lab", row))
    raise NotImplementedError("No example data was in the original data dump, so didn't know how to handle it.")
    properties = {
        "owner_id": "-",
        "testing_facility_saved_name": lab_name,
        "testing_facility_id": lab_id,
        "test_type_label": "Culture",
        "test_type_value": "culture",
        "date_tested": clean_date(column_mapping.get_value("culture_sample_date", row)),
        "date_reported": clean_date(column_mapping.get_value("culture_result_date", row)),
        # NEEDED: Culture type
        # NEEDED: Result
    }
    return properties


def get_dst_test_case_properties(column_mapping, row):
    if column_mapping.get_value("dst_type", row):
        raise NotImplementedError(
            "No example data was in the original data dump, so didn't know how to handle it.")
    # TODO: (WAITING) Return None if this doesn't have anything
    resistance_props = get_dst_test_resistance_properties(column_mapping, row)
    properties = {
        "owner_id": "-",
        "date_tested": clean_date(column_mapping.get_value("dst_sample_date", row)),
        "date_reported": column_mapping.get_value("culture_result_date", row),
    }
    # TODO: (WAITING) Finish this. (waiting on drug details)
    return None



def get_dst_test_resistance_properties(column_mapping, row):
    pass
    # TODO: (WAITING) determine how excel columns map to enikshay drug ids



def get_drug_resistance_case_properties(column_mapping, row):
    resistant_drugs = {
        d['drug_id']: d
        for d in
        get_drug_resistances_from_mehsana_drug_resistance_list(column_mapping, row) +
        get_drug_resistances_from_mumbai_cbnaat(column_mapping, row) +
        get_drug_resistances_from_lpa(column_mapping, row) +
        get_drug_resistances_from_sl_lpa(column_mapping, row)
    }
    additional_drug_case_properties = get_drug_resistances_from_individual_drug_columns(column_mapping, row)
    for drug in additional_drug_case_properties:
        resistant_drugs[drug['drug_id']] = drug
    unknown_cases = generate_unknown_cases(resistant_drugs.keys())
    return resistant_drugs.values() + unknown_cases


def generate_unknown_cases(known_drugs):
    unknown_drugs = set(ALL_DRUGS.keys()) - set(known_drugs)
    return [
        {
            "name": drug_id,
            "owner": "-",
            "drug_id": drug_id,
            "sort_order": ALL_DRUGS[drug_id],
            "sensitivity": "unknown",
        }
        for drug_id in unknown_drugs
    ]


def get_drug_resistances_from_individual_drug_columns(column_mapping, row):
    case_properties = []
    for drug_column_key, drug_id in DRUG_MAP.iteritems():
        value = column_mapping.get_value(drug_column_key, row)
        if value:
            properties = {
                "name": drug_id,
                "owner_id": "-",
                "sensitivity": convert_sensitivity(value),
                "drug_id": drug_id,
                "sort_order": ALL_DRUGS[drug_id],
            }
            case_properties.append(properties)
    return case_properties


def convert_sensitivity(sensitivity_value):
    return {
        "S": "sensitive",
        "R": "resistant",
        "Conta": "unknown",
        "": "unknown",
        "Neg": "unknown",  # TODO: (WAITING) Which should this be?
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


def get_drug_resistances_from_mehsana_drug_resistance_list(column_mapping, row):

    drugs = get_mehsana_resistance_properties(column_mapping, row).get("drug_resistance_list", [])
    if drugs:
        drugs = drugs.split(" ")
    case_properties = []
    for drug in drugs:
        properties = {
            "name": drug,
            "owner_id": "-",
            "sensitivity": "resistant",
            "drug_id": drug,
            "sort_order": ALL_DRUGS[drug],
        }
        case_properties.append(properties)
    return case_properties


def get_drug_resistances_from_mumbai_cbnaat(column_mapping, row):
    # Get the case properties for the drug_resistance cases that should be created as a result of the cbnaat
    # columns in the mumbai mapping
    resistant = get_cbnaat_resistance(column_mapping, row)
    if resistant is not None:
        return [
            {
                "name": "r",
                "owner_id": "-",
                "drug_id": "r",
                "sort_order": ALL_DRUGS["r"],
                "specimen_date": clean_date(column_mapping.get_value("cbnaat_sample_date", row)),
                "result_date": column_mapping.get_value("cbnaat_result_date", row),
                "test_type": "cbnaat",
                "test_type_label": "CBNAAT",
                "sensitivity": "resistant" if resistant else "sensitive",
            }
        ]
    else:
        return []


def get_drug_resistances_from_lpa(column_mapping, row):
    drugs = [
        ("r", clean_mumbai_test_resistance_value(column_mapping.get_value("lpa_rif_result", row))),
        ("h_inha", clean_mumbai_test_resistance_value(column_mapping.get_value("lpa_inh_result", row))),
    ]
    case_props = []
    for drug, resistant in drugs:
        if resistant is not None:
            case_props.append({
                "name": drug,
                "owner_id": "-",
                "drug_id": drug,
                "sort_order": ALL_DRUGS[drug],
                "specimen_date": clean_date(column_mapping.get_value("lpa_sample_date", row)),
                "result_date": column_mapping.get_value("lpa_result_date", row),
                "test_type": "fl_line_probe_assay",
                "test_type_label": "FL LPA",
                "sensitivity": "resistant" if resistant else "sensitive",
            })
    return case_props


def get_drug_resistances_from_sl_lpa(column_mapping, row):
    result = column_mapping.get_value("sl_lpa_result", row)
    if result is None:
        return []
    raise NotImplementedError("No example data was in the original data dump, so didn't know how to handle it.")


def get_follow_up_test_case_properties(column_mapping, row, treatment_initiation_date):
    properties_list = []

    # Mehsana
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
                "test_type_label": "Culture",
                "rft_general": "follow_up_drtb",
            }
            properties["rft_drtb_follow_up_treatment_month"] = get_follow_up_month(
                follow_up, properties['date_tested'], treatment_initiation_date
            )
            properties["result_summary_label"] = result_label(properties['result'])

            properties_list.append(properties)

    # Mumbai
    if hasattr(column_mapping, "follow_up_culture_month_start"):
        month = column_mapping.follow_up_culture_month_start
        while month <= 36:
            if month == 34 or month == 35:
                pass
            else:
                result = column_mapping.get_follow_up_culture_result(month, row)
                if result:
                    date_tested = clean_date(column_mapping.get_follow_up_culture_date(month, row))
                    properties = {
                        "owner_id": "-",
                        "test_type": "culture",
                        "test_type_label": "Culture",
                        "rft_general": "follow_up_drtb",
                        "rft_drtb_follow_up_treatment_month": month,
                        "date_tested": date_tested,
                        "result": clean_result(result),
                    }
                    properties["result_summary_label"] = result_label(properties['result'])
                    properties_list.append(properties)
            month += 1

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


def clean_diabetes_status(xlsx_value):
    if xlsx_value is None:
        return "unknown"
    return {
        "no": "non_diabetic",
        "yes": "diabetic",
    }[xlsx_value.lower()]


def clean_weight_band(value):
    pass
    # TODO: Finish me


def clean_height(value):
    if value is None:
        return None
    if re.match("[0-9]*", str(value)):
        return value
    raise Exception("Invalid height: {}".format(value))


def clean_phone_number(value, digits):
    """
    Phone numbers should be "91" followed by 10 digits. No symbols allowed.
    """
    if not value:
        return None
    assert digits in (10, 12)

    # TODO: (ASK) ask sheel what to do if there are two numbers
    try:
        values = value.split("/")
        value = values[0]
    except AttributeError:
        # This exception will be raised if value is an int.
        pass

    cleaned = re.sub('[^0-9]', '', str(value))
    if len(cleaned) == 12 and cleaned[:2] == "91":
        if digits != 12:
            return cleaned[2:]
    elif len(cleaned) == 10:
        if digits != 10:
            return "91" + cleaned
    return cleaned


def _starts_with_any(value, strings):
    for s in strings:
        if value.startswith(s):
            return True
    return False


def clean_hiv_status(value):
    NON_REACTIVE = "non_reactive"
    REACTIVE = "reactive"
    if not value:
        return None
    if _starts_with_any(value, ["Non Reactive", "NR", "Nr", "NON REACTIVE"]):
        return NON_REACTIVE
    if _starts_with_any(value, ["R ", "Reactive", "Ractive"]) or value == "R":
        return REACTIVE
    return {
        # TODO: (WAITING) Have we mapped pos/neg to reactive/non-reactive correctly?
        "Pos": REACTIVE,
        "Positive": REACTIVE,
        "Negative": NON_REACTIVE,
        "Neg": NON_REACTIVE,
    }[value]


def clean_result(value):
    return {
        None: NO_RESULT,
        "conta": NO_RESULT,
        "Conta": NO_RESULT,
        "CONTA": NO_RESULT,
        "Contaminated": NO_RESULT,
        "NA": NO_RESULT,
        "Neg": NO_RESULT,
        "NEG": NOT_DETECTED,
        "Negative": NOT_DETECTED,
        "Negetive": NOT_DETECTED,
        "negative": NOT_DETECTED,
        "pos": DETECTED,
        "Positive": DETECTED,
        "QNS": NO_RESULT,  # TODO: (WAITING) what should this really be?
    }[value]


def clean_drtb_type(value):
    if value is None:
        return "unknown"
    return {
        "MDR": "mdr",
        "XDR": "xdr",
        "Modified MDR": "mdr",  # TODO: (WAITING) confirm this value
        "RR TB": "rr",
        "MDR TB": "mdr",
        "XDR TB": "xdr",
        "RRTB": "rr",
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
        cleaned_datetime = parse(messy_date_string, dayfirst=False)
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
    location_name, location_id = match_location(domain, xlsx_phi_name, "phi")
    if not location_id:
        raise Exception("A valid phi is required")
    return location_name, location_id


def get_tu(domain, phi_id):
    if not phi_id:
        return None, None
    phi = SQLLocation.get(domain=domain, location_id=phi_id)
    return phi.parent.name, phi.parent.location_id


class Command(BaseCommand):

    MEHSANA_2017 = "mehsana2017"
    MEHSANA_2016 = "mehsana2016"
    MUMBAI = "mumbai"
    FORMATS = [MEHSANA_2016, MEHSANA_2017, MUMBAI]

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
            help="the format of the given excel file. Options are: {}.".format(", ".join(self.FORMATS)),
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

                row_contains_data = any(cell.value for cell in row)
                if not row_contains_data:
                    continue

                try:
                    column_mapping.check_for_required_fields(row)
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

    @classmethod
    def get_column_mapping(cls, format):
        if format == cls.MEHSANA_2016:
            return Mehsana2016ColumnMapping
        elif format == cls.MEHSANA_2017:
            return Mehsana2017ColumnMapping
        elif format == cls.MUMBAI:
            return MumbaiColumnMapping
        else:
            raise Exception("Invalid format. Options are: {}.".format(", ".join(cls.FORMATS)))

    @classmethod
    def get_city_constants(cls, format):
        if format in (cls.MEHSANA_2016, cls.MEHSANA_2017):
            return MehsanaConstants
        elif format == cls.MUMBAI:
            return MumbaiConstants
        else:
            raise Exception("Invalid format. Options are: {}.".format(", ".join(cls.FORMATS)))
