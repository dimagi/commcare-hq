import json
import datetime

from corehq.apps.repeaters.exceptions import RequestConnectionError
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, BasePayloadGenerator
from custom.enikshay.const import (
    PRIMARY_PHONE_NUMBER,
    BACKUP_PHONE_NUMBER,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    TREATMENT_SUPPORTER_PHONE,
    TREATMENT_START_DATE,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
)
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_person_locations,
    get_open_episode_case_from_person,
)
from custom.enikshay.integrations.nikshay.repeaters import (
    NikshayRegisterPatientRepeater,
    NikshayHIVTestRepeater,
    NikshayTreatmentOutcomeRepeater,
)
from custom.enikshay.integrations.nikshay.exceptions import NikshayResponseException
from custom.enikshay.exceptions import NikshayLocationNotFound
from custom.enikshay.integrations.nikshay.field_mappings import (
    gender_mapping,
    occupation,
    episode_site,
    treatment_support_designation,
    patient_type_choice,
    disease_classification,
    dcexpulmonory,
    dcpulmonory,
    treatment_outcome,
    hiv_status,
    art_initiated,
)
from custom.enikshay.case_utils import update_case

ENIKSHAY_ID = 8
NIKSHAY_NULL_DATE = '1900-01-01'


class BaseNikshayPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def _get_credentials(self, repeat_record):
        try:
            username = repeat_record.repeater.username
        except AttributeError:
            username = "tbu-dmdmo01"
        try:
            password = repeat_record.repeater.password
        except AttributeError:
            password = ""

        return username, password

    def _base_properties(self, repeat_record, person_case):
        username, password = self._get_credentials(repeat_record)
        return {
            "regBy": username,
            "regby": username,
            "password": password,
            "Source": ENIKSHAY_ID,
            "IP_From": "127.0.0.1",
            "IP_FROM": "127.0.0.1",
        }

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(repeat_record.domain, repeat_record.payload_id, {"nikshay_error": unicode(exception)})


@RegisterGenerator(NikshayRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class NikshayRegisterPatientPayloadGenerator(BaseNikshayPayloadGenerator):
    def get_payload(self, repeat_record, episode_case):
        """
        https://docs.google.com/document/d/1yUWf3ynHRODyVVmMrhv5fDhaK_ufZSY7y0h9ke5rBxU/edit#heading=h.a9uhx3ql595c
        """
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()

        properties_dict = self._base_properties(repeat_record, person_case)
        properties_dict.update({
            "dotcenter": "NA",
            "Local_ID": person_case.get_id,
        })

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
            _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(e.message))

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


@RegisterGenerator(NikshayTreatmentOutcomeRepeater, 'case_json', 'JSON', is_default=True)
class NikshayTreatmentOutcomePayload(BaseNikshayPayloadGenerator):

    def get_payload(self, repeat_record, episode_case):
        """
        https://docs.google.com/document/d/1yUWf3ynHRODyVVmMrhv5fDhaK_ufZSY7y0h9ke5rBxU/edit#heading=h.6zwqb0ms7iz9
        """
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        base_properties = self._base_properties(repeat_record, person_case)
        nikshay_id = (
            episode_case_properties.get("nikshay_id", None) or
            person_case.dynamic_case_properties().get('nikshay_id')
        )
        base_properties.update({
            "PatientID": nikshay_id,
            "OutcomeDate": episode_case_properties.get(TREATMENT_OUTCOME_DATE),
            "Outcome": treatment_outcome.get(episode_case_properties.get(TREATMENT_OUTCOME)),
            "MO": u"{} {}".format(
                episode_case_properties.get(TREATMENT_SUPPORTER_FIRST_NAME),
                episode_case_properties.get(TREATMENT_SUPPORTER_LAST_NAME),
            ),
            "MORemark": "None Collected in eNikshay",
        })
        return json.dumps(base_properties)

    def handle_success(self, response, payload_doc, repeat_record):
        update_case(payload_doc.domain, payload_doc.case_id, {
            "treatment_outcome_nikshay_registered": "true",
            "treatment_outcome_nikshay_error": "",
        })

    def handle_failure(self, response, payload_doc, repeat_record):
        _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()),
                            "treatment_outcome_nikshay_registered", "treatment_outcome_nikshay_error")


@RegisterGenerator(NikshayHIVTestRepeater, 'case_json', 'JSON', is_default=True)
class NikshayHIVTestPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, person_case):
        """
        https://docs.google.com/document/d/1yUWf3ynHRODyVVmMrhv5fDhaK_ufZSY7y0h9ke5rBxU/edit#heading=h.hxfnqahoeag
        """
        episode_case = get_open_episode_case_from_person(person_case.domain, person_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()
        nikshay_id = (
            episode_case_properties.get("nikshay_id", None) or
            person_case.dynamic_case_properties().get('nikshay_id')
        )
        properties_dict = {
            "PatientID": nikshay_id,
            "HIVStatus": hiv_status.get(person_case_properties.get('hiv_status')),
            "HIVTestDate": datetime.datetime.strptime(
                person_case_properties.get('hiv_test_date', NIKSHAY_NULL_DATE), '%Y-%m-%d'
            ).strftime('%d/%m/%Y'),
            "CPTDeliverDate": datetime.datetime.strptime(
                person_case_properties.get('cpt_initiation_date', NIKSHAY_NULL_DATE), '%Y-%m-%d'
            ).strftime('%d/%m/%Y'),
            "ARTCentreDate": datetime.datetime.strptime(
                person_case_properties.get('art_initiation_date', NIKSHAY_NULL_DATE), '%Y-%m-%d'
            ).strftime('%d/%m/%Y'),
            "InitiatedOnART": art_initiated.get(person_case_properties.get('art_initiated', 'no')),
            "InitiatedDate": datetime.datetime.strptime(
                person_case_properties.get('art_initiation_date', NIKSHAY_NULL_DATE), '%Y-%m-%d'
            ).strftime('%d/%m/%Y'),
            "Source": ENIKSHAY_ID,
            "regby": repeat_record.repeater.username,
            "password": repeat_record.repeater.password,
            "IP_FROM": "127.0.0.1",
        }

        return json.dumps(properties_dict)

    def handle_success(self, response, payload_doc, repeat_record):
        # Simple success message that has {"Nikshay_Message": "Success"...}
        update_case(
            payload_doc.domain,
            payload_doc.case_id,
            {
                "hiv_test_nikshay_registered": "true",
                "hiv_test_nikshay_error": "",
            },
        )

    def handle_failure(self, response, payload_doc, repeat_record):
        _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()),
                            "hiv_test_nikshay_registered", "hiv_test_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, unicode(exception),
                                "hiv_test_nikshay_registered", "hiv_test_nikshay_error")


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
        "pmob": person_case_properties.get(PRIMARY_PHONE_NUMBER, ''),
        "cname": person_case_properties.get('secondary_contact_name_address', ''),
        "caddress": person_case_properties.get('secondary_contact_name_address', ''),
        "cmob": person_case_properties.get(BACKUP_PHONE_NUMBER, ''),
        "pcategory": person_category
    }
    person_locations = get_person_locations(person_case)
    person_properties.update(
        {
            'scode': person_locations.sto,
            'dcode': person_locations.dto,
            'tcode': person_locations.tu,
            'dotphi': person_locations.phi,
        }
    )

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
            [episode_case_properties.get(TREATMENT_SUPPORTER_FIRST_NAME, ''),
             episode_case_properties.get(TREATMENT_SUPPORTER_LAST_NAME, '')])
        ),
        "dotmob": episode_case_properties.get(TREATMENT_SUPPORTER_PHONE, ''),
        # Can this mandatory field be made N/A if in case we don't collect this as in spec
        "dotdesignation": episode_case_properties.get('treatment_supporter_designation', ''),
        "dotpType": treatment_support_designation.get(
            episode_case_properties.get('treatment_supporter_designation', 'other_community_volunteer'),
            treatment_support_designation['other_community_volunteer']
        ),
        "dateofInitiation": episode_case_properties.get(TREATMENT_START_DATE, str(datetime.date.today())),
        "Ptype": patient_type_choice.get(episode_case_properties.get('patient_type_choice', ''), ''),
    })

    return episode_properties


def _save_error_message(domain, case_id, error, reg_field="nikshay_registered", error_field="nikshay_error"):
    update_case(
        domain,
        case_id,
        {
            reg_field: "false",
            error_field: error,
        },
    )
