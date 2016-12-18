import json
import datetime

from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, CaseRepeaterJsonPayloadGenerator, BasePayloadGenerator
from custom.enikshay.case_utils import get_occurrence_case_from_episode, get_person_case_from_occurrence
from custom.enikshay.integrations.nikshay.repeaters import NikshayRegisterPatientRepeater
from custom.enikshay.integrations.nikshay.field_mappings import (
 gender_mapping, occupation, episode_site,
 treatment_support_designation, patient_type_choice,
 disease_classification
)


ENIKSHAY_ID = 8


# This might have issue with CaseRepeaterJsonPayloadGenerator
@RegisterGenerator(NikshayRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class NikshayRegisterPatientPayloadGenerator(CaseRepeaterJsonPayloadGenerator):
    def get_payload(self, repeat_record, episode_case):
        occurence_case = get_occurrence_case_from_episode(repeat_record.domain, episode_case.get_id)
        person_case = get_person_case_from_occurrence(repeat_record.domain, occurence_case.get_id)
        episode_case_properties = episode_case.get_dynamic_properties()

        state_location = SQLLocation.objects.get(location_id=episode_case_properties['current_address_state_choice'])
        district_location = SQLLocation.objects.get(location_id=episode_case_properties[
         'current_address_district_choice'])
        tu_location = SQLLocation.objects.get(location_id=person_case.get('tu_choice'))
        dot_phi_location = SQLLocation.objects.get(location_id=person_case.get('phi_assigned_to'))

        return json.dumps(
            {"scode": state_location.metadata['nikshay_code'],
             "dcode": district_location.metadata['nikshay_code'],
             "pname": (episode_case_properties.get('first_name', '') +
                       episode_case_properties.get('last_name', '')
                       ), # person_case.case_name
             "pgender": gender_mapping.get(person_case.get('sex', ''), ''),
             "page": person_case.get('age', ''),
             "paddress": person_case.get('current_address', ''),
             "poccupation": occupation.get(episode_case_properties.get('occupation', occupation['other'])),
             "pregdate": (episode_case.get('date_of_registration', str(datetime.date.today()))),
             "ptbyr": (str(datetime.datetime.strptime(
              (episode_case.get('date_of_registration', str(datetime.date.today())))).year)),
             "disease_classification": disease_classification.get(episode_case_properties.get(
              'basis_of_diagnosis', ''), ''),
             "sitedetail": episode_site.get(episode_case_properties.get('site_choice', ''), ''),
             "dotname": (episode_case_properties.get('treatment_supporter_first_name', '') +
                         episode_case_properties.get('treatment_supporter_last_name', '')
                         ),
             "dotdesignation": "N/A",
             "dotpType": treatment_support_designation.get(episode_case_properties.get(
              'treatment_supporter_designation', ''), ''),
             "tcode": tu_location.metadata['nikshay_code'],
             "dotphi": dot_phi_location.metadata['nikshay_code'],
             "cname": person_case.get('secondary_contact_name_address', ''),
             "caddress": person_case.get('secondary_contact_name_address', ''),
             "dateofInitiation": episode_case.get('treatment_initiation_date', str(datetime.date.today())),
             "Ptype": patient_type_choice.get(episode_case.get('patient_type_choice', ''), ''),
             "pcategory": "2", # n/a
             "pmob": episode_case_properties.get('phone_number', ''),
             "cmob": episode_case_properties.get('secondary_contact_phone_number', ''),
             "dotmob": episode_case_properties.get('treatment_supporter_mobile_number', ''),
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

             "regBy": self.repeater.username,
             # "IP_Address": "mk-ip-address",
             # "IP_From": "127.0.0.1",
             "Local_ID": repeat_record.get_id,
             "Source": ENIKSHAY_ID
             }
        )
