"""
# DRTB Case import

This management imports cases into HQ from a given excel file.

The script supports importing three different excel file formats (mumbai, mehsana2016, and mehsana2017), although
only mumbai is complete!!

## Usage

NOTE: You should be sure to save all excel files processed by this management command and the csv files it
produces. These will be essential for debugging the import should any issues arise later.

Example:
```
$ ./manage.py import_drtb_cases enikshay drtb_cases.xlsx mumbai
```
(This is a dry run because no `--commit` flag is passed)

Each run of the script is assigned an id, based on the current time.
Every run (dry or otherwise) will output two csv log files.

"drtb-import-<import id>.csv" lists the case ids that were created, or the exception that was raised for each row
of the import file.

"bad-rows-<import id>.csv" lists each row that was not imported successfully, and the error message for that row.
This document is useful for sending back to EY for cleaning. The document also includes the original row, so
a cleaner can:
- open this document
- fix each error *in the same document* according to the error message
- delete the first two columns (which list row number and error message)
- send the document back to dimagi for re-import
Then you can simply run the script with the modified document

I've also created a companion management command to help debug issues that may occur. I'm imaging the following
types of requests coming in from the field:

1. "John Doe was in the spreadsheet, but I can't find him in the app"
In this case, you'll want to be able to match a row from the import to a commcare case.
You can run
```
$ ./manange.py drtb_import_history get_outcome <spreadsheet row> <import id>
```
This will parse the "drtb-import-<import id>.csv" created by `improt_drtb_cases`, and print either a list of case
ids created, or the error message that was raised in processing that row

2. "This case in the app is in an inconsistent state, I think something might have gone wrong with the import"
In this case, you will want to be able to match a case id to the spreadsheet row that it was generated from.
You can run:
```
$ ./manange.py drtb_import_history get_row <case_id> <import id>
```
This will output a row number.


## Design

The spec is located [here](https://docs.google.com/spreadsheets/d/1Pz-cYNvo5BkF-Sta1ol4ZzfBYIQ4kGlZ3FdJgBLe5WE/edit#gid=1273583155)
and defines how each row in the excel sheet should be mapped to commcare cases. Each row corresponds to multiple
cases (sometimes dozens).

You'll probably notice that a fair number of the `clean_<field name>()` functions are pretty lame, and just check
if the given value is in some list. There has been a bit of churn on the requirements for this script, so at an
earlier time these functions did more sophisticated conversion of messy values in the xlsx to values that matched
our app. However it was eventually decided to have EY clean all the excel sheets before hand, which is why those
functions don't do much now. I probably wouldn't have used this architecture if I was writing this from scratch.

The main components of the script are as follows:


## `ColumnMapping`
This class allows accessing the values in an excel sheet row by a normalized column name. e.g.
```
ColumnMapping.get_value("age", row)
```
This will return the age value from the row. The normalized column names are useful because the column index will
differ between formats. This also makes it easy to change the index->column name mapping should anyone happen to
add columns to the sheet without telling you :)

### <LOCATION>_MAP
Each `ColumnMapping` references a dictionary (e.g. MUMBAI_MAP) that maps the normalized column names to column
indexes)


## `MumbaiConstants`/`MehsanaConstants`
These classes hold constants specific to their respective locations which are used to populate some case properties


## `get_case_structures_from_row()`
This is where the magic happens. The row is converted to CaseStructure objects, which will alter be submited to HQ
with the CaseFactory if this isn't a dry run. Various helper functions extract case property dicts from the row
for each case, then convert these to CaseStructure objects.
"""

import csv
import decimal
import logging
import datetime
import traceback
import uuid

import re
from collections import namedtuple

from dateutil.parser import parse
from django.core.management import (
    BaseCommand,
)
from django.db import models

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.ota.utils import update_device_id
from corehq.util.workbook_reading import open_any_workbook
from custom.enikshay.case_utils import CASE_TYPE_PERSON, CASE_TYPE_OCCURRENCE, CASE_TYPE_EPISODE, CASE_TYPE_TEST, \
    CASE_TYPE_DRUG_RESISTANCE, CASE_TYPE_SECONDARY_OWNER
from custom.enikshay.two_b_datamigration.models import MigratedDRTBCaseCounter
from custom.enikshay.user_setup import compress_nikshay_id
from dimagi.utils.decorators.memoized import memoized

logger = logging.getLogger('two_b_datamigration')


DETECTED = "tb_detected"
NOT_DETECTED = "tb_not_detected"
NO_RESULT = "no_result"


class ValidationFailure(Exception):
    pass


class FieldValidationFailure(ValidationFailure):
    def __init__(self, value, column_name, *args, **kwargs):
        self.value = value
        self.column_name = column_name
        msg = "Unexpected value in {} column: {}".format(column_name, value)
        super(FieldValidationFailure, self).__init__(msg, *args, **kwargs)


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
    "social_scheme": 15,
    "key_populations": 16,
    "initial_home_visit_date": 18,
    "aadhaar_number": 19,
    "district_name": 22,
    "phi_name": 25,
    "reason_for_testing": 27,
    "site_of_disease": 28,
    "type_of_patient": 29,
    "weight": 30,
    "weight_band": 31,
    "height": 32,
    "hiv_status": 33,
    "hiv_test_date": 34,
    "hiv_program_id": 35,
    "cpt_initiation_date": 36,
    "art_initiation_date": 37,
    "diabetes": 38,
    "cbnaat_lab": 39,  # This is similar to testing_facility, but slightly different
    "cbnaat_lab_number": 40,
    "cbnaat_sample_date": 41,
    "cbnaat_result": 42,
    "cbnaat_result_date": 43,
    "lpa_lab": 44,
    "lpa_lab_number": 45,
    "lpa_sample_date": 46,
    "lpa_rif_result": 47,
    "lpa_inh_result": 48,
    "lpa_result_date": 49,
    "sl_lpa_lab": 50,
    "sl_lpa_lab_number": 51,
    "sl_lpa_sample_date": 52,
    "sl_lpa_result": 53,
    "sl_lpa_result_date": 54,
    "culture_lab": 55,
    "culture_lab_number": 56,
    "culture_sample_date": 57,
    "culture_type": 58,
    "culture_result": 59,
    "culture_result_date": 60,
    "dst_sample_date": 61,
    "dst_type": 62,
    "Lfx": 63,  # Levo
    "Eto": 64,  # Ethio
    # "Cyclo": 65,  # TODO: (WAITING) unknown drug mapping
    "E": 66,  # Etham
    "Z": 67,  # PZA
    "Km": 68,  # Kana
    "Cm": 69,  # Capr
    "Mfx (0.5)": 70,  # Moxi
    "Mfx (2.0)": 71,  # High dose Moxi
    "Cfz": 72,  # Clofa
    "Lzd": 73,  # Line
    "H (0.4)": 74,
    "H (0.1)": 75,  # High dose INH
    "PAS": 76,  # Na-Pas
    # "Oflox": 77,  # TODO: (WAITING) unknown drug mapping
    "S": 78,
    "Clr": 79,
    "R": 80,  # Rif
    # "Amoxyclav": 81,  # TODO: (WAITING) unknown drug mapping
    "Am": 82,
    "dst_result_date": 83,
    "treatment_initiation_date": 89,
    "treatment_regimen": 93,
    "ip_to_cp_date": 95,
    "treatment_outcome": 200,
    "date_of_treatment_outcome": 201,
}


# A map of column identifier to the corresponding app drug id
DRUG_COLUMN_TO_APP_ID_MAP = {
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

# A map of drug names used in the mumbai sheet to drug ids
DRUG_NAME_TO_ID_MAPPING = {
    "Levo": "lfx",
    "Ethio": "eto",
    "Cyclo": None,  # TODO: (Waiting)
    "Etham": "e",
    "PZA": "z",
    "Kana": "km",
    "Capr": "cm",
    "Moxi": "mfx_05",
    "High dose Moxi": "mfx_20",
    "Clofa": "cfz",
    "Line": "lzd",
    "INH": "h_katg",
    "High dose INH": "h_inha",
    "Na-Pas": "pas",
    "Oflox": None,  # TODO: (Waiting)
    "Streptomycin": "s",
    "Clarithromycin": "clr",
    "Rif": "r",
    "Amoxyclav": None,  # TODO: (Waiting)
    "Amikacin": "am",
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
                raise ValidationFailure("{} is required".format(key))


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
    follow_up_culture_index_start = 96
    follow_up_culture_month_start = 3

    @classmethod
    def get_follow_up_culture_result(cls, month, row):
        index = cls._get_follow_up_start_index(month)
        try:
            return row[index].value
        except IndexError:
            return None

    @classmethod
    def get_follow_up_culture_lab(cls, month, row):
        index = cls._get_follow_up_start_index(month) + 1
        try:
            return row[index].value
        except IndexError:
            return None

    @classmethod
    def get_follow_up_culture_date(cls, month, row):
        index = cls._get_follow_up_start_index(month) + 2
        try:
            return row[index].value
        except IndexError:
            return None

    @classmethod
    def _get_follow_up_start_index(cls, month):
        if month == 36:
            # For some reason the sheet jumps from 33 to 36, so just special casing it.
            index = 170
        else:
            assert month >= 3 and month <= 33
            offset = (month - 3) * 3
            index = cls.follow_up_culture_index_start + offset
        return index


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


def get_case_structures_from_row(commit, domain, migration_id, column_mapping, city_constants, row):
    """
    Return a list of CaseStructure objects corresponding to the information in the given row.
    """
    person_case_properties = get_person_case_properties(domain, column_mapping, row)
    occurrence_case_properties = get_occurrence_case_properties(column_mapping, row)
    episode_case_properties = get_episode_case_properties(domain, column_mapping, city_constants, row)
    test_case_properties = get_test_case_properties(
        domain, column_mapping, row, episode_case_properties['treatment_initiation_date'])
    drug_resistance_case_properties = get_drug_resistance_case_properties(column_mapping, row)
    secondary_owner_case_properties = get_secondary_owner_case_properties(
        domain, city_constants, person_case_properties['dto_id'])

    # We do this as a separate step because we don't want to generate ids if there is going to be an exception
    # raised while generating the other properties.
    update_cases_with_readable_ids(
        commit, domain, person_case_properties, occurrence_case_properties, episode_case_properties,
        secondary_owner_case_properties
    )

    # Close the occurrence if we have a treatment outcome recorded
    close_occurrence = ("treatment_outcome" in episode_case_properties and
                        episode_case_properties["treatment_outcome"])

    person_case_structure = get_case_structure(CASE_TYPE_PERSON, person_case_properties, migration_id)
    occurrence_case_structure = get_case_structure(
        CASE_TYPE_OCCURRENCE, occurrence_case_properties, migration_id, host=person_case_structure,
        close=close_occurrence)
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
    secondary_owner_case_structures = [
        get_case_structure(CASE_TYPE_SECONDARY_OWNER, props, migration_id, host=occurrence_case_structure)
        for props in secondary_owner_case_properties
    ]

    return [
        person_case_structure,
        occurrence_case_structure,
        episode_case_structure,
    ] + secondary_owner_case_structures + drug_resistance_case_structures + test_case_structures


def update_cases_with_readable_ids(commit, domain, person_case_properties, occurrence_case_properties,
                                   episode_case_properties, secondary_owner_case_properties):
    phi_id = person_case_properties['owner_id']
    person_id_flat = _PersonIdGenerator.generate_person_id_flat(domain, phi_id, commit)
    person_id = _PersonIdGenerator.get_person_id(person_id_flat)
    occurrence_id = person_id + "-O1"
    episode_id = person_id + "-E1"

    person_case_properties['person_id'] = person_id
    person_case_properties['person_id_flat'] = person_id_flat
    occurrence_case_properties["occurrence_id"] = occurrence_id
    occurrence_case_properties["name"] = occurrence_id
    episode_case_properties['episode_id'] = episode_id
    episode_case_properties['name'] = episode_id
    for secondary_owner in secondary_owner_case_properties:
        secondary_owner['name'] = occurrence_id + secondary_owner['secondary_owner_type']


def get_case_structure(case_type, properties, migration_identifier, host=None, close=False):
    """
    Converts a properties dictionary to a CaseStructure object
    """
    owner_id = properties.pop("owner_id")
    props = {k: v for k, v in properties.iteritems() if v is not None}
    props['created_by_migration'] = migration_identifier
    props['migration_data_source'] = "excel_document"
    kwargs = {
        "case_id": uuid.uuid4().hex,
        "walk_related": False,
        "attrs": {
            "case_type": case_type,
            "create": True,
            "owner_id": owner_id,
            "update": props,
            "close": close,
        },
    }
    if host:
        kwargs['indices'] = [CaseIndex(
            host,
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type=host.attrs['case_type'],
        )]
    return CaseStructure(**kwargs)


def get_person_case_properties(domain, column_mapping, row):
    person_name = column_mapping.get_value("person_name", row)
    xlsx_district_name = column_mapping.get_value("district_name", row)
    district_name, district_id = match_district(domain, xlsx_district_name)
    phi_name, phi_id = match_phi(domain, column_mapping.get_value("phi_name", row))
    tu_name, tu_id = get_tu(domain, phi_id)
    age = clean_age_entered(column_mapping.get_value("age_entered", row))

    properties = {
        "name": person_name,
        "dto_name": district_name,
        "dto_id": district_id,
        "owner_id": phi_id,
        "manual_nikshay_id": "yes",
        "current_episode_type": "confirmed_drtb",
        "nikshay_id": column_mapping.get_value("nikshay_id", row),
        "sex": clean_sex(column_mapping.get_value("sex", row)),
        "age_entered": age,
        "age": age,
        "dob": calculate_dob(column_mapping.get_value("age_entered", row)),
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
        "diabetes_status": clean_diabetes_status(column_mapping.get_value("diabetes", row)),
        "language_code": "hin",
        "case_version": "20",
    }

    properties.update(get_disease_site_properties_for_person(column_mapping, row))

    if properties["cpt_initiation_date"]:
        properties["cpt_initiated"] = "yes"
    if properties["art_initiation_date"]:
        properties["art_initiated"] = "yes"

    phone_number = column_mapping.get_value("phone_number", row)
    if phone_number:
        clean_number = clean_phone_number(phone_number)
        contact_number = clean_contact_phone_number(clean_number)
        properties['contact_phone_number'] = contact_number
        properties['phone_number'] = clean_number

    social_scheme = column_mapping.get_value("social_scheme", row)
    properties["socioeconomic_status"] = clean_socioeconomic_status(social_scheme)

    return properties


def get_occurrence_case_properties(column_mapping, row):
    initial_visit_date = column_mapping.get_value("initial_home_visit_date", row)
    properties = {
        "owner_id": "-",
        "current_episode_type": "confirmed_drtb",
        "initial_home_visit_status": "completed" if initial_visit_date else None,
        "initial_home_visit_date": clean_date(initial_visit_date),
        'name': 'Occurrence #1',
        'occurrence_episode_count': 1,
    }
    properties.update(get_disease_site_properties(column_mapping, row))
    properties.update(get_key_populations(column_mapping, row))

    return properties


def get_episode_case_properties(domain, column_mapping, city_constants, row):
    phi_name, phi_id = match_phi(domain, column_mapping.get_value("phi_name", row))
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
        "treatment_initiating_drtb_center_id": city_constants.drtb_center_id,
        "episode_type": "confirmed_drtb",
        "episode_pending_registration": "no",
        "is_active": "yes",
        "diagnosing_facility_id": phi_id,
        "diagnosing_facility_name": phi_name,
        "date_of_diagnosis": report_sending_date,
        "diagnosis_test_result_date": report_sending_date,
        "treatment_initiation_date": treatment_initiation_date,
        "treatment_card_completed_date": treatment_card_completed_date,
        "regimen_change_history": get_episode_regimen_change_history(
            column_mapping, row, treatment_initiation_date),
        "pmdt_tb_number": column_mapping.get_value("drtb_number", row),
        "treatment_status_other": column_mapping.get_value("reason_for_not_initiation_on_treatment", row),
        "treatment_outcome": get_treatment_outcome(column_mapping, row),
        "treatment_outcome_date": clean_date(column_mapping.get_value("date_of_treatment_outcome", row)),
        "weight": column_mapping.get_value("weight", row),
        "weight_band": clean_weight_band(column_mapping.get_value("weight_band", row)),
        "height": clean_height(column_mapping.get_value("height", row)),
        "diagnosis_test_specimen_date": clean_date(column_mapping.get_value("cbnaat_sample_date", row)),
        "treatment_regimen": clean_treatment_regimen(column_mapping.get_value("treatment_regimen", row)),
        "patient_type_choice": clean_patient_type(column_mapping.get_value("type_of_patient", row))
    }

    # this code is specifically for Mehsana since we dont' have a treatment status in Mumbai
    # need to update once we get Excel to figure out how to determine treatment initiating facility ID
    raw_treatment_status = column_mapping.get_value("treatment_status", row)
    if raw_treatment_status:
        treatment_status_id = convert_treatment_status(raw_treatment_status)
        properties["treatment_status"] = treatment_status_id
        if treatment_status_id not in ("other", "", None):
            properties["treatment_initiated"] = "yes_phi"

    properties.update(get_selection_criteria_properties(column_mapping, row))
    if treatment_initiation_date:
        properties["treatment_initiated"] = "yes_phi"
        if 'treatment_status' not in properties:
            properties["treatment_initiating_facility_id"] = phi_id
            properties['treatment_status'] = 'initiated_second_line_treatment'

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
    value = column_mapping.get_value("reason_for_testing", row)
    if not value:
        return {}
    clean_value = value.lower()

    rft_drtb_diagnosis_ext_dst_tmonth = None
    if isinstance(clean_value, (int, float, decimal.Decimal)):
        rft_drtb_diagnosis = "extended_dst"
        rft_drtb_diagnosis_ext_dst = "3_monthly_culture_positives"
        rft_drtb_diagnosis_ext_dst_tmonth = value
    else:
        try:
            rft_drtb_diagnosis, rft_drtb_diagnosis_ext_dst = {
                "at diagnosis": ["mdr_at_diagnosis", None],
                "contact of mdr/rr tb": ["contact_of_mdr_rr", None],
                "follow up sm+ve at end of ip and cp": ["follow_up_sm_ve_ip", None],
                "private referral": ["private_referral", None],
                "discordance resolution": ["discordance_resolution", None],
                "mdr/rr at diagnosis": ["extended_dst", "mdr_rr_diagnosis"],
                "more than 4 months culture positive": ["extended_dst", "4mo_culture_positive"],
                "3 monthly, for persistent culture positive": ["extended_dst", "3_monthly_culture_positives"],
                "failure of mdr/rr-tb regimen": ["extended_dst", "mdr_rr_failure"],
                "culture reversion": ["extended_dst", "culture_reversion"],
                "recurrent case of second line treatment": ["extended_dst", "recurrent_second_line_treatment"],
            }[clean_value]
        except KeyError:
            raise FieldValidationFailure(value, "Reason for Testing")

    return {
        "rft_general": "diagnosis_drtb",
        "rft_drtb_diagnosis": rft_drtb_diagnosis,
        "rft_drtb_diagnosis_ext_dst": rft_drtb_diagnosis_ext_dst,
        "rft_drtb_diagnosis_ext_dst_tmonth": rft_drtb_diagnosis_ext_dst_tmonth,
    }


def get_diagnosis_properties(column_mapping, domain, row):
    properties = {}
    diagnosing_test = None
    if column_mapping.get_value("cbnaat_result", row):
        diagnosing_test = get_cbnaat_test_case_properties(domain, column_mapping, row)
    elif column_mapping.get_value("lpa_rif_result", row) or column_mapping.get_value("lpa_inh_result", row):
        diagnosing_test = get_lpa_test_case_properties(domain, column_mapping, row)
    elif column_mapping.get_value("sl_lpa_result", row):
        diagnosing_test = get_sl_lpa_test_case_properties(domain, column_mapping, row)

    if diagnosing_test:
        properties["diagnosis_test_type_label"] = diagnosing_test['test_type_label']
        properties["diagnosis_test_type_value"] = diagnosing_test['test_type_value']
        properties["diagnosis_test_drug_resistance_list"] = diagnosing_test['drug_resistance_list']
        properties["diagnosis_test_drug_sensitive_list"] = diagnosing_test['drug_sensitive_list']
        properties["diagnosis_lab_facility_id"] = diagnosing_test['testing_facility_id']
        properties["diagnosis_lab_facility_name"] = diagnosing_test['testing_facility_name']
        properties["diagnosis_test_result_date"] = diagnosing_test['date_reported']
        properties["diagnosis_test_specimen_date"] = diagnosing_test['date_tested']
        properties["diagnosis_test_summary"] = diagnosing_test['result_summary_display']

    return properties
    # TODO: (WAITING) figure out how to set these properties based on other info


def get_disease_site_properties(column_mapping, row):
    xlsx_value = column_mapping.get_value("site_of_disease", row)
    if not xlsx_value:
        return {}

    value = xlsx_value.replace('EP ', 'extra pulmonary ').\
        lower().\
        replace('extra pulmonary', 'extra_pulmonary').\
        replace('lymph node', 'lymph_node').\
        replace('pleural effusion', 'pleural_effusion')

    if (not re.match("^extra_pulmonary \(other - .*$", value)
        and value not in [
        "pulmonary",
        "extra_pulmonary",
        "extra_pulmonary ",
        "extra_pulmonary (lymph_node)",
        "extra_pulmonary (spine)",
        "extra_pulmonary (brain)",
        "extra_pulmonary (pleural_effusion)",
        "extra_pulmonary (abdominal)",
        "extra_pulmonary (other)",
    ]):
        raise FieldValidationFailure(xlsx_value, "site of disease")
    classification = "extra_pulmonary" if "extra_pulmonary" in value else "pulmonary"
    match = re.match("^.*\((.*)\)", value)
    if match:
        site = match.groups()[0]
        if re.match("^other - .*$", site):
            site_choice = site.replace('other - ', '')
            site = 'other'
        else:
            site_choice = None
    else:
        site = None
        site_choice = None
    return {
        "disease_classification": classification,
        "site_detail": site,
        "site_choice": site_choice
    }


def get_key_populations(column_mapping, row):
    value = column_mapping.get_value("key_populations", row)
    if not value:
        return {}
    clean_value = value.lower()
    try:
        key_populations, key_population_other_detail = {
            "slum dweller": ["slum_dweller", None],
            "migrant": ["migrant", None],
            "contact of known tb patients": ["known_patient_contact", None],
            "refugee": ["refugee", None],
            "other (health care worker)": ["health_care_worker", None],
            "other (minor)": ["other", "minor"],
            "other (diabetic)": ["other", "diabetic"],
            "other (na)": [None, None],
            "na": [None, None],
        }[clean_value]
    except KeyError:
        raise FieldValidationFailure(value, "Key Populations")

    return {
        "key_populations": key_populations,
        "key_population_other_detail": key_population_other_detail,
    }


def get_disease_site_properties_for_person(column_mapping, row):
    props = get_disease_site_properties(column_mapping, row)
    return {"current_{}".format(k): v for k, v in props.iteritems()}


def get_treatment_outcome(column_mapping, row):
    value = column_mapping.get_value("treatment_outcome", row)
    if not value:
        return None
    clean_value = value.lower().replace(' ', '_')
    if clean_value not in [
            "cured",
            "died",
            "treatment_complete",
            "failure",
            "loss_to_follow_up",
            "regimen_changed",
            "pediatric_failure_to_respond",
            "not_evaluated",
            "treatment_failure_culture_non_reversion",
            "treatment_failure_culture_reversion",
            "treatment_failure_additional_drug_resistance",
            "treatment_failure_adverse_drug_reaction",
        ]:
        raise FieldValidationFailure(value, "treatment outcome")
    return clean_value


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
        ("r", clean_mumbai_lpa_resistance_value(column_mapping.get_value("lpa_rif_result", row))),
        ("h_inha", clean_mumbai_lpa_resistance_value(column_mapping.get_value("lpa_inh_result", row))),
    ]
    return {
        "drug_sensitive_list": " ".join(
            [drug for drug, resistant in drug_resistances if (not resistant) and (resistant is not None)]),
        "drug_resistance_list": " ".join([drug for drug, resistant in drug_resistances if resistant])
    }


def get_sl_lpa_test_resistance_properties(column_mapping, row):
    result = column_mapping.get_value("sl_lpa_result", row)
    if result is None:
        return {}
    drugs = result.split(",")
    for drug in drugs:
        drug = drug.strip()
        if drug not in DRUG_NAME_TO_ID_MAPPING.keys():
            raise FieldValidationFailure(result, "SLPA result")
    properties = {
        "drug_resistant_list": " ".join(filter(None, [DRUG_NAME_TO_ID_MAPPING[drug_name] for drug_name in drugs])),
    }
    return properties


def get_test_summary(properties):
    if properties['result'] == 'tb_detected':
        detected = 'TB Detected'
    else:
        detected = 'TB Not Detected'

    return '\n'.join(filter(None, [
        detected,
        'Resistant: {}'.format(properties['drug_resistance_list']) if properties['drug_resistance_list'] else None,
        'Sensitive: {}'.format(properties['drug_sensitive_list']) if properties['drug_sensitive_list'] else None,
    ]))


def get_cbnaat_resistance(column_mapping, row):
    value = column_mapping.get_value("cbnaat_result", row)
    if value is None:
        return None
    if value not in ["sensitive", "resistant"]:
        raise FieldValidationFailure(value, "cbnaat result")
    return value == "resistant"


def clean_mumbai_lpa_resistance_value(value):
    return {
        None: None,
        "Not tested": None,
        "R": True,
        "Resistant": True,
        "Sensitive": False,
        "S": False,
    }[value]


def clean_sex(value):
    if not value:
        return None
    return {
        "female": "female",
        "male": "male",
        "f": "female",
        "m": "male",
        "transgender": "transgender"
    }[value.lower()]


def clean_age_entered(value):
    if not isinstance(value, (int, float, decimal.Decimal)):
        raise FieldValidationFailure(value, "age")
    return value


def calculate_dob(value):
    age = clean_age_entered(value)
    dob = datetime.date.today() - datetime.timedelta(days=age * 365)
    return str(dob)


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

    if column_mapping.get_value("cbnaat_result", row):
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
        "testing_facility_name": facility_name,
        "testing_facility_id": facility_id,
    }
    properties.update(get_selection_criteria_properties(column_mapping, row))
    properties.update(get_mehsana_resistance_properties(column_mapping, row))
    return properties


def get_cbnaat_test_case_properties(domain, column_mapping, row):
    cbnaat_lab_name, cbnaat_lab_id = match_facility(domain, column_mapping.get_value("cbnaat_lab", row))
    date_reported = column_mapping.get_value("cbnaat_result_date", row)
    if not date_reported:
        raise ValidationFailure("cbnaat result date required if result given")

    properties = {
        "owner_id": "-",
        "date_reported": date_reported,
        "testing_facility_name": cbnaat_lab_name,
        "testing_facility_id": cbnaat_lab_id,
        "lab_serial_number": column_mapping.get_value("cbnaat_lab_number", row),
        "test_type_label": "CBNAAT",
        "test_type_value": "cbnaat",
        "date_tested": clean_date(column_mapping.get_value("cbnaat_sample_date", row)),
        "result": "tb_not_detected",
        "drug_resistance_list": '',
        "drug_sensitive_list": '',
    }

    properties.update(get_cbnaat_test_resistance_properties(column_mapping, row))
    if get_cbnaat_resistance(column_mapping, row) is not None:
        properties['result'] = "tb_detected"
    properties['result_summary_display'] = get_test_summary(properties)
    return properties


def get_lpa_test_case_properties(domain, column_mapping, row):
    lpa_lab_name, lpa_lab_id = match_facility(domain, column_mapping.get_value("cbnaat_lab", row))
    result_date = clean_date(column_mapping.get_value("lpa_result_date", row))
    if not result_date:
        raise ValidationFailure("LPA result date required if result included")

    properties = {
        "owner_id": "-",
        "testing_facility_name": lpa_lab_name,
        "testing_facility_id": lpa_lab_id,
        "lab_serial_number": column_mapping.get_value("lpa_lab_number", row),
        "test_type_label": "FL LPA",
        "test_type_value": "fl_line_probe_assay",
        "date_tested": clean_date(column_mapping.get_value("lpa_sample_date", row)),
        "date_reported": result_date,
        "result": "tb_not_detected",
        "drug_resistance_list": '',
        "drug_sensitive_list": '',
    }

    properties.update(get_lpa_test_resistance_properties(column_mapping, row))
    if properties['drug_resistance_list']:
        properties['result'] = "tb_detected"
    properties['result_summary_display'] = get_test_summary(properties)
    return properties


def get_sl_lpa_test_case_properties(domain, column_mapping, row):
    sl_lpa_lab_name, sl_lpa_lab_id = match_facility(domain, column_mapping.get_value("cbnaat_lab", row))
    date_reported = clean_date(column_mapping.get_value("lpa_result_date", row))
    if not date_reported:
        raise ValidationFailure("LPA result date required if result included")
    properties = {
        "owner_id": "-",
        "testing_facility_name": sl_lpa_lab_name,
        "testing_facility_id": sl_lpa_lab_id,
        "lab_serial_number": column_mapping.get_value("sl_lpa_lab_number", row),
        "test_type_label": "SL LPA",
        "test_type_value": "sl_line_probe_assay",
        "date_tested": clean_date(column_mapping.get_value("lpa_sample_date", row)),
        "date_reported": date_reported,
        "result": "tb_not_detected",
        "drug_resistance_list": '',
        "drug_sensitive_list": '',
    }

    properties.update(get_sl_lpa_test_resistance_properties(column_mapping, row))
    if properties['drug_resistance_list']:
        properties['result'] = "tb_detected"
    properties['result_summary_display'] = get_test_summary(properties)
    return properties


def get_culture_test_case_properties(domain, column_mapping, row):
    lab_name, lab_id = match_facility(domain, column_mapping.get_value("cbnaat_lab", row))
    culture_type = clean_culture_type(column_mapping.get_value("culture_type", row))
    date_reported = clean_date(column_mapping.get_value("culture_result_date", row))
    if not date_reported:
        raise ValidationFailure("Culture date reported required if result included")

    properties = {
        "owner_id": "-",
        "testing_facility_name": lab_name,
        "testing_facility_id": lab_id,
        "lab_serial_number": column_mapping.get_value("culture_lab_number", row),
        "test_type_value": "culture",
        "date_tested": clean_date(column_mapping.get_value("culture_sample_date", row)),
        "date_reported": date_reported,
        "culture_type": culture_type,
        "test_type_label": get_culture_type_label(culture_type) or 'Culture',
        "result": clean_result(column_mapping.get_value("culture_result", row))
    }
    properties['result_summary_display'] = get_test_summary(properties)
    return properties


def clean_culture_type(value):
    if not value:
        return None
    clean_value = value.lower()
    try:
        return {
            "lc": "lc",
            "lj": "lj",
            "liquid": "lc",
        }[clean_value]
    except KeyError:
        raise FieldValidationFailure(value, "Culture Type")


def get_culture_type_label(culture_type):
    return {
        None: None,
        "lc": "Culture (LC)",
        "lj": "Culture (LJ)",
    }[culture_type]


def get_dst_test_case_properties(column_mapping, row):
    resistance_props = get_dst_test_resistance_properties(column_mapping, row)
    if resistance_props['drug_resistant_list'] or resistance_props['drug_sensitive_list']:
        properties = {
            "owner_id": "-",
            "date_tested": clean_date(column_mapping.get_value("dst_sample_date", row)),
            "date_reported": column_mapping.get_value("dst_result_date", row),
            "dst_test_type": column_mapping.get_value("dst_type", row),
        }
        properties.update(resistance_props)
        return properties
    return None


def get_dst_test_resistance_properties(column_mapping, row):
    resistant_drugs = []
    sensitive_drugs = []
    for drug_column_key, drug_id in DRUG_COLUMN_TO_APP_ID_MAP.iteritems():
        value = column_mapping.get_value(drug_column_key, row)
        if value:
            sensitivity = convert_sensitivity(value)
            if sensitivity == "sensitive":
                sensitive_drugs.append(drug_id)
            elif sensitivity == "resistant":
                resistant_drugs.append(drug_id)

    return {
        "drug_resistant_list": " ".join(resistant_drugs),
        "drug_sensitive_list": " ".join(sensitive_drugs),
    }


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
            "owner_id": "-",
            "drug_id": drug_id,
            "sort_order": ALL_DRUGS[drug_id],
            "sensitivity": "unknown",
        }
        for drug_id in unknown_drugs
    ]


def get_drug_resistances_from_individual_drug_columns(column_mapping, row):
    case_properties = []
    for drug_column_key, drug_id in DRUG_COLUMN_TO_APP_ID_MAP.iteritems():
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
    if not sensitivity_value:
        return "unknown"
    return {
        "sensitive": "sensitive",
        "resistant": "resistant",
        "unknown": "unknown",
        "s": "sensitive",
        "r": "resistant",
        "conta": "unknown",
        "": "unknown",
    }[sensitivity_value.lower()]


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


def clean_patient_type(value):
    if not value:
        return None

    clean_value = value.lower().replace(' ', '_')
    if clean_value not in [
        "new",
        "recurrent",
        "treatment_after_failure",
        "treatment_after_ltfu",
        "other_previously_treated",
        None
    ]:
        raise FieldValidationFailure(value, "type of patient")
    return clean_value


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
        ("r", clean_mumbai_lpa_resistance_value(column_mapping.get_value("lpa_rif_result", row))),
        ("h_inha", clean_mumbai_lpa_resistance_value(column_mapping.get_value("lpa_inh_result", row))),
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
    case_props = []
    drug_list_string = get_sl_lpa_test_resistance_properties(column_mapping, row).get("drug_resistant_list", "")
    drugs = drug_list_string.split(" ")
    for drug in [x for x in drugs if x != ""]:
        case_props.append({
            "name": drug,
            "owner_id": "-",
            "drug_id": drug,
            "sort_order": ALL_DRUGS[drug],
            "specimen_date": clean_date(column_mapping.get_value("sl_lpa_sample_date", row)),
            "result_date": column_mapping.get_value("sl_lpa_result_date", row),
            "test_type": "sl_line_probe_assay",
            "test_type_label": "SL LPA",
            "sensitivity": "resistant",
        })
    return case_props


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
                    lab_name = column_mapping.get_follow_up_culture_lab(month, row)
                    properties = {
                        "owner_id": "-",
                        "test_type": "culture",
                        "test_type_label": "Culture",
                        "testing_facility_name": lab_name,
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


def get_secondary_owner_case_properties(domain, city_constants, district_id):
    name, loc_id = get_drtb_hiv_location(domain, district_id)
    return [
        {
            "secondary_owner_name": city_constants.drtb_center_name,
            "secondary_owner_type": "drtb",
            "owner_id": city_constants.drtb_center_id,
        },
        {
            "secondary_owner_name": name,
            "secondary_owner_type": "drtb-hiv",
            "owner_id": loc_id,
        }
    ]


def clean_diabetes_status(value):
    if not value:
        return None
    clean_value = value.lower().replace(' ', '_')
    try:
        return {
            "diabetic": "diabetic",
            "positive": "diabetic",
            "non_diabetic": "non_diabetic",
            "negative": "non_diabetic",
            "unknown": "unknown",
        }[clean_value]
    except KeyError:
        raise FieldValidationFailure(value, "Diabetes status")


def clean_weight_band(value):
    if not value:
        return None
    try:
        return {
            "Less than 16": "drtb_conventional_lt_16",
            "16-29": "drtb_conventional_16_29",
            "30-45": "drtb_conventional_30_45",
            "16-25": "drtb_conventional_old_16_25",
            "26-45": "drtb_conventional_old_26_45",
            "46-70": "drtb_conventional_46_70",
            "Above 70": "drtb_conventional_gt70"
        }[value]
    except KeyError:
        raise FieldValidationFailure(value, "Weight Band")


def clean_height(value):
    if value is None:
        return None
    if re.match("[0-9]*", str(value)):
        return value
    raise FieldValidationFailure(value, "height")


def clean_treatment_regimen(value):
    if not value:
        return None
    try:
        return {
            "Regimen for XDR TB": "xdr",
            "Regimen for MDR/RR TB": "mdr_rr",
            "Modified Regimen for MDR/RR-TB + FQ/SLI resistance": "mdr_rr_fq_sli",
            "Regimen with New Drug for MDR-TB Regimen + FQ/SLI resistance": "new_drug_mdr_rr_fq_sli",
            "Regimen with New Drug for XDR-TB": "new_drug_xdr",
            "Modified regimen for mixed pattern resistance": "mixed_pattern",
            "Regimen for INH mono/poly resistant TB": "inh_poly_mono",
            "Regimen with New Drug for failures of regimen for MDR TB": "new_fail_mdr",
        }[value]
    except KeyError:
        raise FieldValidationFailure(value, "Treatment Regimen")


def clean_phone_number(value):
    """
    Convert the phone number to the 10 digit format if possible, else return the misformated number
    """
    if not value:
        return None

    if not isinstance(value, (basestring, int)):
        raise FieldValidationFailure(value, "phone number")

    try:
        values = value.split("/")
        value = values[0]
    except AttributeError:
        # This exception will be raised if value is an int.
        pass

    cleaned = re.sub('[^0-9]', '', str(value))

    if len(cleaned) == 12 and cleaned[:2] == "91":
        return cleaned[2:]
    elif len(cleaned) == 11 and cleaned[0] == "0":
        return cleaned[1:]
    else:
        return cleaned


def clean_contact_phone_number(clean_phone_number):
    """
    :param clean_phone_number: A string returned by clean_phone_number()
    :return: The phone number in 12 digit format if clean_phone_number was 10 digits, otherwise None.
    """
    if not clean_phone_number:
        return None
    elif len(clean_phone_number) == 10:
        return "91" + clean_phone_number
    else:
        return None


def _starts_with_any(value, strings):
    for s in strings:
        if value.startswith(s):
            return True
    return False


def clean_hiv_status(value):
    if not value:
        return None
    clean_value = value.lower().replace(' ', '_')
    try:
        return {
            "reactive": "reactive",
            "non_reactive": "non_reactive",
            "positive": "reactive",
            "negative": "non_reactive",
            "unknown": "unknown",
        }[clean_value]
    except KeyError:
        raise FieldValidationFailure(value, "HIV status")


def clean_socioeconomic_status(value):
    if value is None:
        return "unknown"
    return {
        "bpl": "bpl",
        "apl": "apl",
        "unknown": "unknown",
    }[value.lower()]


def clean_result(value):
    return {
        None: NO_RESULT,
        NO_RESULT: NO_RESULT,
        NOT_DETECTED: NOT_DETECTED,
        DETECTED: DETECTED,
        "Sample rejected": NO_RESULT,
        "Result awaited": NO_RESULT,
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
    }[value]


def clean_drtb_type(value):
    if value is None:
        return "unknown"
    if value not in [
        "mdr",
        "xdr",
        "rr",
        "pdr",
        "mr",
        "unknown",
    ]:
        raise FieldValidationFailure(value, "DRTB type")
    return value


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
        if messy_date_string == "?":
            return None

        # The excel library we use should actually import dates correctly if the column format is date.
        raise Exception("Got a date like {}".format(messy_date_string))

        # I think some columns are month/day/year and some are day/month/year
        # cleaned_datetime = parse(messy_date_string, dayfirst=False)
        # return cleaned_datetime.date()


def match_district(domain, xlsx_district_name):
    return match_location(domain, xlsx_district_name, "dto")


@memoized
def match_location(domain, xlsx_name, location_type=None):
    """
    Given location name taken from the spreadsheet, return the name and id of the matching location in HQ.
    """
    if not xlsx_name:
        return None, None
    xlsx_name = xlsx_name.strip()

    default_query_kwargs = {"domain": domain}
    if location_type:
        default_query_kwargs["location_type__code"] = location_type

    try:
        kwargs = {"name__iexact": xlsx_name}
        kwargs.update(default_query_kwargs)
        location = SQLLocation.active_objects.get(**kwargs)
    except SQLLocation.DoesNotExist:
        possible_matches = (SQLLocation.active_objects
                            .filter(**default_query_kwargs)
                            .filter(models.Q(name__icontains=xlsx_name)))
        if len(possible_matches) == 1:
            location = possible_matches[0]
        elif len(possible_matches) > 1:
            raise ValidationFailure("Multiple location matches for {}".format(xlsx_name))
        else:
            raise ValidationFailure("No location matches for {}".format(xlsx_name))
    return location.name, location.location_id


def match_facility(domain, xlsx_facility_name):
    """
    Given lab facility name taken from the spreadsheet, return the name and id of the matching location in HQ.
    """
    if not xlsx_facility_name:
        return None, None
    elif "other" in xlsx_facility_name.lower():
        return xlsx_facility_name, None
    else:
        # this is really ugly but some rows have a lab code
        # our site codes are prepended with cdst and cbnaat
        try:
            return match_location(domain, xlsx_facility_name, location_type="cdst")
        except ValidationFailure:
            try:
                cbnaat_facility_name = "cbnaat_" + xlsx_facility_name.strip().replace('-', '_').lower()
                return match_location(domain, cbnaat_facility_name, location_type="cdst")
            except ValidationFailure:
                cdst_facility_name = "cdst_" + xlsx_facility_name.strip().replace('-', '_').lower()
                return match_location(domain, cdst_facility_name, location_type="cdst")


def match_phi(domain, xlsx_phi_name):
    location_name, location_id = match_location(domain, xlsx_phi_name, "phi")
    if not location_id:
        raise ValidationFailure("A valid phi is required")
    return location_name, location_id


def get_tu(domain, phi_id):
    if not phi_id:
        return None, None
    phi = SQLLocation.active_objects.get(domain=domain, location_id=phi_id)
    return phi.parent.name, phi.parent.location_id


def get_drtb_hiv_location(domain, district_id):
    if not district_id:
        return None, None
    drtb_hiv = SQLLocation.active_objects.get(
        domain=domain,
        parent__location_id=district_id,
        location_type__code="drtb-hiv"
    )
    return drtb_hiv.name, drtb_hiv.location_id


class _PersonIdGenerator(object):
    """
    Person cases in eNikshay require unique, human-readable ids.
    These ids are generated by combining a user id, device id, and serial count for the user/device pair

    This script is its own "device", and in --commit runs, the serial count is maintained in a database to insure
    that the next number is always unique.
    """

    dry_run_counter = 0

    @classmethod
    def _next_serial_count(cls, commit):
        if commit:
            return MigratedDRTBCaseCounter.get_next_counter()
        else:
            cls.dry_run_counter += 1
            return cls.dry_run_counter

    @classmethod
    def _next_serial_count_compressed(cls, commit):
        return compress_nikshay_id(cls._next_serial_count(commit), 2)

    @classmethod
    def get_id_issuer_body(cls, user):
        id_issuer_body = user.user_data['id_issuer_body']
        assert id_issuer_body
        return id_issuer_body

    @classmethod
    def get_user(cls, domain, phi_id):
        users = get_users_by_location_id(domain, phi_id)
        for user in sorted(users, lambda u: u.username):
            if user.user_data['id_issuer_body']:
                return user
        raise Exception("No suitable user found at location {}".format(phi_id))

    @classmethod
    def id_device_body(cls, user, commit):
        script_device_id = "drtb-case-import-script"
        update_device_id(user, script_device_id)
        if commit:
            user.save()
        index = [x.device_id for x in user.devices].index(script_device_id)
        return compress_nikshay_id(index + 1, 0)

    @classmethod
    def generate_person_id_flat(cls, domain, phi_id, commit):
        """
        Generate a flat person id. If commit is False, this id will only be unique within this run of the
        management command, it won't be unique between runs.
        """
        user = cls.get_user(domain, phi_id)
        return (
            cls.get_id_issuer_body(user) +
            cls.id_device_body(user, commit) +
            cls._next_serial_count_compressed(commit)
        )

    @classmethod
    def get_person_id(cls, person_id_flat):
        """
        Create a more human readable version of the flat person id.
        """
        num_chars_between_hyphens = 3
        return '-'.join([
            person_id_flat[i:i + num_chars_between_hyphens]
            for i in range(0, len(person_id_flat), num_chars_between_hyphens)
        ])


ImportFormat = namedtuple("ImportFormat", "column_mapping constants header_rows")


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
        migration_id = self.generate_id()
        self.log_meta_info(migration_id, options['commit'])
        import_format = self.get_import_format(format)
        case_factory = CaseFactory(domain)

        import_log_file_name = "drtb-import-{}.csv".format(migration_id)
        bad_rows_file_name = "{}-bad-rows.csv".format(migration_id)
        rows_with_unknown_exceptions = 0

        with open_any_workbook(excel_file_path) as workbook, \
                open(bad_rows_file_name, "w") as bad_rows_file, \
                open(import_log_file_name, "w") as import_log_file:

            import_log_writer = csv.writer(import_log_file)
            bad_rows_file_writer = csv.writer(bad_rows_file)
            import_log_writer.writerow(["row", "case_ids", "exception"])

            for i, row in enumerate(workbook.worksheets[0].iter_rows()):
                if i < import_format.header_rows:
                    # Skip the headers rows
                    if i == 0:
                        extra_cols = ["original import row number", "error message"]
                    else:
                        extra_cols = [None, None]
                    bad_rows_file_writer.writerow(extra_cols + [c.value for c in row])
                    continue

                row_contains_data = any(cell.value for cell in row)
                if not row_contains_data:
                    continue

                try:
                    import_format.column_mapping.check_for_required_fields(row)
                    case_structures = get_case_structures_from_row(
                        options['commit'], domain, migration_id, import_format.column_mapping,
                        import_format.constants, row
                    )
                    import_log_writer.writerow([i, ",".join(x.case_id for x in case_structures)])
                    logger.info("Creating cases for row {}".format(i))

                    if options['commit']:
                        case_factory.create_or_update_cases(case_structures)
                except Exception as e:
                    logger.info("Creating case structures for row {} failed".format(i))
                    if isinstance(e, ValidationFailure):
                        exception_as_string = e.message
                    else:
                        rows_with_unknown_exceptions += 1
                        exception_as_string = traceback.format_exc()
                    import_log_writer.writerow([i, "", exception_as_string])
                    bad_rows_file_writer.writerow([i, exception_as_string] + [c.value for c in row])

        print "{} rows with unknown exceptions".format(rows_with_unknown_exceptions)

    def generate_id(self):
        now = datetime.datetime.now()
        # YYYY-MM-DD_HHMMSS
        format = "%Y-%m-%d_%H%M%S"
        return now.strftime(format)

    @staticmethod
    def log_meta_info(migration_id, commit):
        logger.info("Starting DRTB import with id {}".format(migration_id))
        if commit:
            logger.info("This is a REAL RUN")
        else:
            logger.info("This is a dry run")

    @classmethod
    def get_import_format(cls, format_string):
        if format_string == cls.MEHSANA_2016:
            return ImportFormat(
                Mehsana2016ColumnMapping,
                MehsanaConstants,
                1,
            )
        elif format_string == cls.MEHSANA_2017:
            return ImportFormat(
                Mehsana2017ColumnMapping,
                MehsanaConstants,
                1,
            )
        elif format_string == cls.MUMBAI:
            return ImportFormat(
                MumbaiColumnMapping,
                MumbaiConstants,
                2,
            )
        else:
            raise Exception("Invalid format. Options are: {}.".format(", ".join(cls.FORMATS)))

