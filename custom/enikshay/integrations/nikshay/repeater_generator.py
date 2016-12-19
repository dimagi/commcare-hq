import json
import datetime

from simplejson import JSONDecodeError

from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, CaseRepeaterJsonPayloadGenerator
from custom.enikshay.case_utils import get_person_case_from_episode
from custom.enikshay.integrations.nikshay.repeaters import NikshayRegisterPatientRepeater
from custom.enikshay.integrations.nikshay.field_mappings import (
    gender_mapping, occupation, episode_site,
    treatment_support_designation, patient_type_choice,
    disease_classification
)
from custom.enikshay.integrations.ninetyninedots.repeater_generators import _update_person_case

ENIKSHAY_ID = 8


@RegisterGenerator(NikshayRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class NikshayRegisterPatientPayloadGenerator(CaseRepeaterJsonPayloadGenerator):
    def get_payload(self, repeat_record, episode_case):
        """
        mandatory_fields for Nikshay Registration API as of now
        scode
        dcode
        pname
        pgender
        paddress
        pmob
        ptbyr
        pregdate
        cname
        caddress
        cmob
        dcpulmunory # Pending
        dotname
        dotdesignation
        dotmob
        dotpType
        dotcenter # Pending
        regBy # Used date_of_diagnosis instead of date_of_registration
        IP_From # Pending
        Local_ID
        tcode # Pending
        page
        poccupation
        dotphi
        Ptype
        pcategory # Pending
        Source
        """
        # properties skipped with example values
        # "plandline": "N/A",
        # "clandline": "N/A",
        # "dotlandline": "N/A",
        # "cvisitedby": "N/A",
        # "cvisitedDate": "N/A",
        # "dotcenter": "N/A",
        # "dotmoname": "N/A",
        # "mosign": "N/A",
        # "mosigndonedate": "N/A",
        # "atbtreatment": "N/A",
        # "atbduration": ,
        # "atbsource": "G",
        # "atbregimen": "Manish-Regim",
        # "atbyr": "2015",
        # "dcpulmunory": "P",
        # "IP_Address": "mk-ip-address",
        # "IP_From": "127.0.0.1",
        person_case = get_person_case_from_episode(repeat_record.domain, episode_case.get_id)

        episode_case_properties = episode_case.case_properties()
        person_case_properties = person_case.case_properties()

        properties_dict = {
            "regBy": self.repeater.username,
            "Local_ID": person_case.get_id,
            "Source": ENIKSHAY_ID
        }
        properties_dict.update(_get_person_case_properties(person_case_properties))
        properties_dict.update(_get_episode_case_properties(episode_case_properties))
        return json.dumps(properties_dict)

    def handle_success(self, response, payload_doc, repeat_record):
        # A success would be getting a nikshay_id for the patient
        # without it this would actually be a failure
        try:
            nikshay_id = response.json()['Results']['Fieldvalue']
            person_case_id = get_person_case_from_episode(payload_doc.domain, payload_doc.case_id).get_id
            _update_person_case(
                payload_doc.domain,
                person_case_id,
                {
                    "nikshay_registered": "true",
                    "nikshay_id": nikshay_id
                }
            )
        except (JSONDecodeError, KeyError):
            self.handle_failure(response, payload_doc, repeat_record)

    def handle_failure(self, response, payload_doc, repeat_record):
        try:
            error_message = response.json().get('Results', response.content)
        except (JSONDecodeError, KeyError):
            error_message = response.content
        save_error_message(response.status_code, error_message)


def _get_person_case_properties(person_case_properties):
    state_choice = person_case_properties.get('current_address_state_choice', None)
    district_choice = person_case_properties.get('current_address_district_choice', None)

    if state_choice:
        state_location = (SQLLocation.objects.
                          get(location_id=person_case_properties['current_address_state_choice']))
    if district_choice:
        district_location = (SQLLocation.objects.
                             get(location_id=person_case_properties['current_address_district_choice']))

    # Could not locate this in any of the case types : episode, person, occurence
    # tu_location = SQLLocation.objects.get(location_id=person_case_properties.get('tu_choice'))
    # "tcode": tu_location.metadata['nikshay_code'],
    # and pcategory
    person_properites = {
        "pname": person_case_properties.get('name', ''),
        "pgender": gender_mapping.get(person_case_properties.get('sex', ''), ''),
        "page": person_case_properties.get('age', ''),
        "paddress": person_case_properties.get('current_address', ''),
        "pmob": person_case_properties.get('contact_phone_number', ''),
        "dotphi": person_case_properties.get('phi', ''),
        "cname": person_case_properties.get('secondary_contact_name_address', ''),
        "caddress": person_case_properties.get('secondary_contact_name_address', ''),
        "cmob": person_case_properties.get('secondary_contact_phone_number', ''),
    }

    if state_location:
        person_properites['scode'] = state_location.metadata.get('nikshay_code', '')
    if district_location:
        person_properites['dcode'] = district_location.metadata.get('nikshay_code')

    # {'dcode': u'JLR', 'paddress': u'123, near asdf, , , Jalore, Rajasthan ', 'cmob': u'1234567890',
    # 'pname': u'home visit', 'scode': u'RJ', 'dotphi': u'Test S1-C1-D1-T1 PHI 1', 'pmob': u'1234567890',
    # 'cname': u'123', 'caddress': u'123', 'pgender': 'T', 'page': u'79'}
    return person_properites


def _get_episode_case_properties(episode_case_properties):
    episode_site_choice = episode_site.get(episode_case_properties.get('site_choice', None))
    if episode_site_choice:
        site_detail = episode_site.get(episode_site_choice, 'others')
    episode_case_date = episode_case_properties.get('date_of_diagnosis', None)
    if episode_case_date:
        episode_date = datetime.datetime.strptime(episode_case_date, "%Y-%m-%d").date()
    else:
        episode_date = datetime.date.today()

    episode_year = episode_date.year
    episode_properties = {
        "poccupation": occupation.get(
            episode_case_properties.get('occupation', 'other'),
            occupation['other']
        ),
        "pregdate": str(episode_date),
        "ptbyr": str(episode_year),
        "disease_classification": disease_classification.get(
            episode_case_properties.get('disease_classification', ''),
            ''
        ),
        "dotname": (episode_case_properties.get('treatment_supporter_first_name', '') +
                    episode_case_properties.get('treatment_supporter_last_name', '')
                    ),
        "dotmob": episode_case_properties.get('treatment_supporter_mobile_number', ''),
        # Can this mandatory field be made N/A if in case we don't collect this as in spec
        "dotdesignation": episode_case_properties.get('treatment_supporter_designation', ''),
        "dotpType": treatment_support_designation.get(
            episode_case_properties.get('treatment_supporter_designation', 'other_community_volunteer'),
            treatment_support_designation['other_community_volunteer']
        ),
        "dateofInitiation": episode_case_properties.get('treatment_initiation_date', str(datetime.date.today())),
        "Ptype": patient_type_choice.get(episode_case_properties.get('patient_type_choice', ''), ''),
        "sitedetail": site_detail
    }

    # Example : {'dateofInitiation': '2016-12-01', 'pregdate': '2016-12-01', 'dotdesignation': u'tbhv_to',
    # 'ptbyr': '2016', 'dotpType': '7', 'dotmob': u'1234567890', 'dotname': u'asdfasdf', 'Ptype': '1',
    # 'poccupation': 1, 'disease_classification': 'P'}
    return episode_properties


def save_error_message(repeat_record, status_code, error_message):
    repeat_record.add_failure_reason(
        "{}: {}".format(status_code, error_message)
    )
