import json
import datetime

from corehq.apps.locations.models import SQLLocation

from corehq.apps.users.models import CouchUser
from corehq.apps.repeaters.exceptions import RequestConnectionError
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, BasePayloadGenerator
from custom.enikshay import const
from custom.enikshay.case_utils import get_person_case_from_episode
from custom.enikshay.integrations.nikshay.repeaters import NikshayRegisterPatientRepeater
from custom.enikshay.integrations.nikshay.exceptions import (
    NikshayResponseException,
    NikshayLocationNotFound,
    NikshayCodeNotFound,
)
from custom.enikshay.integrations.nikshay.field_mappings import (
    gender_mapping,
    occupation,
    episode_site,
    treatment_support_designation,
    patient_type_choice,
    disease_classification,
    dcexpulmonory,
    dcpulmonory,
)
from custom.enikshay.case_utils import update_case

ENIKSHAY_ID = 8


@RegisterGenerator(NikshayRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class NikshayRegisterPatientPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

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
        dcpulmunory
        dotname
        dotdesignation
        dotmob
        dotpType
        dotcenter
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
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)

        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()
        properties_dict = {
            "regBy": "tbu-dmdmo01",  # TODO: change this to a real username, store in localsettings
            "Local_ID": person_case.get_id,
            "Source": ENIKSHAY_ID,
            "dotcenter": "NA",
            "IP_From": "127.0.0.1",
        }
        try:
            properties_dict.update(_get_person_case_properties(person_case, person_case_properties))
        except NikshayLocationNotFound as e:
            _save_error_message(person_case.domain, person_case.case_id, e)
        properties_dict.update(_get_episode_case_properties(episode_case_properties))
        return json.dumps(properties_dict)

    def handle_success(self, response, payload_doc, repeat_record):
        # A success would be getting a nikshay_id for the patient
        # without it this would actually be a failure
        try:
            nikshay_id = _get_nikshay_id_from_response(response)
            update_case(
                payload_doc.domain,
                payload_doc.case_id,
                {
                    "nikshay_registered": "true",
                    "nikshay_id": nikshay_id,
                    "nikshay_error": "",
                },
                external_id=nikshay_id,
            )
        except NikshayResponseException as e:
            _save_error_message(payload_doc.domain, payload_doc.case_id, e.message)

    def handle_failure(self, response, payload_doc, repeat_record):
        if response.status_code == 409:  # Conflict
            update_case(
                payload_doc.domain,
                payload_doc.case_id,
                {
                    "nikshay_registered": "true",
                    "nikshay_error": "duplicate",
                },
            )
        else:
            _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()))

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, unicode(exception))


def _get_nikshay_id_from_response(response):
    try:
        response_json = response.json()
    except ValueError:
        raise NikshayResponseException("Invalid JSON received")

    try:
        message = response_json['Nikshay_Message']
        if message == "Success":
            results = response_json['Results']
            nikshay_ids = [result['Fieldvalue'] for result in results if result['FieldName'] == 'NikshayId']
        else:
            raise NikshayResponseException("Nikshay message was: {}".format(message))
    except KeyError:
        raise NikshayResponseException("Response JSON not to spec: {}".format(response_json))

    if len(nikshay_ids) == 1:
        return nikshay_ids[0]
    else:
        raise NikshayResponseException("No Nikshay ID received: {}".format(response_json))


def get_person_locations(person_case):
    location_properties = {}
    try:
        phi_location = SQLLocation.objects.get(location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=person_case.owner_id, person_id=person_case.case_id)
        )

    try:
        tu_location = phi_location.parent
        district_location = tu_location.parent
        city_location = district_location.parent
        state_location = city_location.parent
    except AttributeError:
        raise NikshayLocationNotFound("Location structure error for person: {}".format(person_case.case_id))
    try:
        # TODO: verify how location codes will be stored
        location_properties['scode'] = state_location.metadata['nikshay_code']
        location_properties['dcode'] = district_location.metadata['nikshay_code']
        location_properties['tcode'] = tu_location.metadata['nikshay_code']
        location_properties['dotphi'] = phi_location.metadata['nikshay_code']
    except (KeyError, AttributeError) as e:
        raise NikshayCodeNotFound("Nikshay codes not found: {}".format(e))

    return location_properties


def _get_person_case_properties(person_case, person_case_properties):
    """
    :return: Example {'dcode': u'JLR', 'paddress': u'123, near asdf, Jalore, Rajasthan ', 'cmob': u'1234567890',
    'pname': u'home visit', 'scode': u'RJ', 'tcode': 'AB', dotphi': u'Test S1-C1-D1-T1 PHI 1',
    'pmob': u'1234567890', 'cname': u'123', 'caddress': u'123', 'pgender': 'T', 'page': u'79', 'pcategory': 1}
    """
    person_category = '2' if person_case_properties.get('previous_tb_treatment', '') == 'yes' else '1'
    person_properties = {
        "pname": person_case.name,
        "pgender": gender_mapping.get(person_case_properties.get('sex', ''), ''),
        "page": person_case_properties.get('age', ''),
        "paddress": person_case_properties.get('current_address', ''),
        "pmob": person_case_properties.get(const.PRIMARY_PHONE_NUMBER, ''),
        "cname": person_case_properties.get('secondary_contact_name_address', ''),
        "caddress": person_case_properties.get('secondary_contact_name_address', ''),
        "cmob": person_case_properties.get(const.BACKUP_PHONE_NUMBER, ''),
        "pcategory": person_category
    }
    person_properties.update(get_person_locations(person_case))

    return person_properties


def _get_episode_case_properties(episode_case_properties):
    """
    :return: Example : {'dateofInitiation': '2016-12-01', 'pregdate': '2016-12-01', 'dotdesignation': u'tbhv_to',
    'ptbyr': '2016', 'dotpType': '7', 'dotmob': u'1234567890', 'dotname': u'asdfasdf', 'Ptype': '1',
    'poccupation': 1, 'disease_classification': 'P', 'sitedetail: 1}
    """
    episode_properties = {}

    episode_site_choice = episode_case_properties.get('site_choice', None)
    if episode_site_choice:
        site_detail = episode_site.get(episode_site_choice, 'others')
        episode_properties["sitedetail"] = site_detail

    episode_case_date = episode_case_properties.get('date_of_diagnosis', None)
    if episode_case_date:
        episode_date = datetime.datetime.strptime(episode_case_date, "%Y-%m-%d").date()
    else:
        episode_date = datetime.date.today()

    episode_year = episode_date.year
    episode_properties.update({
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
        "dcpulmunory": dcpulmonory.get(episode_case_properties.get('disease_classification', ''), "N"),
        "dcexpulmunory": dcexpulmonory.get(episode_case_properties.get('disease_classification', ''), "N"),
        "dotname": (' '.join(
            [episode_case_properties.get('treatment_supporter_first_name', ''),
             episode_case_properties.get('treatment_supporter_last_name', '')])
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
    })

    return episode_properties


def _save_error_message(domain, case_id, error):
    update_case(
        domain,
        case_id,
        {
            "nikshay_registered": "false",
            "nikshay_error": error,
        },
    )
