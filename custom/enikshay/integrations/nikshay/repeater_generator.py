import json
import datetime

from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.exceptions import RequestConnectionError
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, BasePayloadGenerator
from custom.enikshay.const import (
    PRIMARY_PHONE_NUMBER,
    BACKUP_PHONE_NUMBER,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    TREATMENT_SUPPORTER_PHONE,
    TREATMENT_START_DATE,
)
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_person_locations,
    get_open_episode_case_from_occurrence,
    get_open_episode_case_from_person,
    get_lab_referral_from_test,
    get_occurrence_case_from_test,
    get_person_case_from_occurrence
)
from custom.enikshay.integrations.nikshay.repeaters import NikshayRegisterPatientRepeater
from custom.enikshay.integrations.nikshay.exceptions import NikshayResponseException
from custom.enikshay.exceptions import (
    NikshayLocationNotFound,
    RequiredValueMissing,
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
    purpose_of_testing,
    smear_result_grade,
    hiv_status,
    art_initiated,
)
from custom.enikshay.case_utils import update_case

ENIKSHAY_ID = 8
NIKSHAY_NULL_DATE = '1990-01-01'


@RegisterGenerator(NikshayRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class NikshayRegisterPatientPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, episode_case):
        """
        https://docs.google.com/document/d/1yUWf3ynHRODyVVmMrhv5fDhaK_ufZSY7y0h9ke5rBxU/edit#heading=h.a9uhx3ql595c
        """
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()

        try:
            username = repeat_record.repeater.username
        except AttributeError:
            username = "tbu-dmdmo01"
        try:
            password = repeat_record.repeater.password
        except AttributeError:
            password = ""

        properties_dict = {
            "regBy": username,
            "password": password,
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


class NikshayFollowupPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, test_case):
        """
        "PatientID": "Nikshay-ID",
        "TestDate": "dd/mm/yyyy",
        "LabNo": "23",
        "RegBy": "nikshay-user",
        "Local_ID": "patients-case-id",
        "IP_From": "Servers IP address or Mobile device MAC Address",
        "IntervalId": 0:4,
        "PatientWeight": 45,
        "SmearResult": 0:99,
        "Source": nikshay-id,
        "DMC": owner_id
        """
        self.test_case = test_case
        dmc_code = self._get_dmc_code()
        occurence_case = get_occurrence_case_from_test(test_case.domain, test_case.get_id)
        episode_case = get_open_episode_case_from_occurrence(test_case.domain, occurence_case.get_id)
        person_case = get_person_case_from_occurrence(test_case.domain, occurence_case.get_id)

        test_case_properties = test_case.dynamic_case_properties()
        episode_case_properties = episode_case.dynamic_case_properties()

        interval_id, lab_serial_number, result_grade = self._get_mandatory_fields(test_case_properties)

        test_conducted_on = self._formatted_date(test_case_properties.get('date_tested'))
        # example output for
        # https://india.commcarehq.org/a/enikshay/reports/case_data/39d45f04-3005-4ea1-8692-a5bf1e7ff685/
        # weird smear result: test_case_properties.get('result_grade') was 'scanty'
        # LabNo to be integrated as case property
        # DMC code seems off for this record. its a string on characters
        # {'LabNo': 0, 'Local_ID': u'89e14931-4930-4862-9ce7-723856cf27f1', 'RegBy': 'tbu-dmdmo01',
        # 'DMC': u'XXQADMC', 'Source': 8, 'TestDate': '06/08/2016', 'SmearResult': 0, 'PatientID': None,
        # 'IntervalId': 0, 'IP_From': '127.0.0.1'}
        properties_dict = {
            "PatientID": episode_case_properties.get('nikshay_id'),
            "TestDate": test_conducted_on,
            "LabNo": lab_serial_number,
            "RegBy": repeat_record.repeater.username,
            "password": repeat_record.repeater.password,
            "Local_ID": person_case.get_id,
            "IP_From": "127.0.0.1",
            "IntervalId": interval_id,
            # since weight is not taken and is mandatory we send 1
            "PatientWeight": test_case_properties.get('weight', 1),
            "SmearResult": result_grade,
            "Source": ENIKSHAY_ID,
            "DMC": dmc_code
        }

        return json.dumps(properties_dict)

    def _get_mandatory_fields(self, test_case_properties):
        # list of fields that we want the case to have and should raise an exception if its missing or not in
        # expected state to highlight missing essentials in repeat records. Check added here instead of
        # allow_to_forward to bring to notice these records instead of silently ignoring them
        interval_id = self._get_interval_id(test_case_properties.get('purpose_of_testing'),
                                            test_case_properties.get('follow_up_test_reason'))

        lab_serial_number = test_case_properties.get('lab_serial_number', None)
        test_result_grade = test_case_properties.get('result_grade', None)
        bacilli_count = test_case_properties.get('bacilli_count', None)
        result_grade = smear_result_grade.get(test_result_grade, bacilli_count)

        if any(mandatory_value is None for mandatory_value in [lab_serial_number, result_grade]):
            raise RequiredValueMissing("Mandatory value missing in one of the following "
                                       "LabSerialNo: {lab_serial_number}, ResultGrade: {result_grade}"
                                       .format(lab_serial_number=lab_serial_number,
                                               result_grade=test_result_grade))
        return interval_id, lab_serial_number, result_grade

    def get_result_grade(self, test_result_grade, bacilli_count):
        if test_result_grade in smear_result_grade.keys():
            return smear_result_grade.get(test_result_grade)
        elif test_result_grade == 'scanty':
            return smear_result_grade.get("SC-{b_count}".format(b_count=bacilli_count), None)

    def _formatted_date(self, value):
        return datetime.datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')

    def _get_interval_id(self, testing_purpose, follow_up_test_reason):
        if testing_purpose == 'diagnostic':
            interval_id = 0
        else:
            interval_id = purpose_of_testing.get(follow_up_test_reason, None)
        if interval_id is None:
            raise RequiredValueMissing("Value missing for intervalID, purpose_of_testing: {testing_purpose}, "
                                       "follow_up_test_reason: {follow_up_test_reason}".format(
                                        testing_purpose=testing_purpose,
                                        follow_up_test_reason=follow_up_test_reason
                                       ))
        return interval_id

    def _get_dmc_code(self):
        lab_referral_case = get_lab_referral_from_test(self.test_case.domain, self.test_case.get_id)
        dmc = SQLLocation.active_objects.get_or_None(location_id=lab_referral_case.owner_id)
        if not dmc:
            raise NikshayLocationNotFound(
                "Location with id: {location_id} not found."
                "This is the owner for lab referral with id: {lab_referral_case_id}"
                .format(location_id=lab_referral_case.owner_id, lab_referral_case_id=lab_referral_case.case_id)
            )
        nikshay_code = dmc.metadata.get('nikshay_code')
        if not nikshay_code or (isinstance(nikshay_code, (str, unicode)) and not nikshay_code.isdigit()):
            raise RequiredValueMissing("InAppt value for dmc, got value: {}".format(nikshay_code))
        return dmc.metadata.get('nikshay_code')

    def handle_success(self, response, payload_doc, repeat_record):
        # Simple success message that has {"Nikshay_Message": "Success"...}
        update_case(
            payload_doc.domain,
            payload_doc.case_id,
            {
                "nikshay_registered": "true",
                "nikshay_error": "",
            },
        )

    def handle_failure(self, response, payload_doc, repeat_record):
        _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()))


class NikshayHIVTestPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, person_case):
        """
        "PatientID": "Nikshay-ID",
        "HIVStatus": "Pos/Neg/Unknown",
        "HIVTestDate": "dd/mm/yyyy",
        "CPTDeliverDate": "dd/mm/yyyy",
        "ARTCentreDate": "dd/mm/yyyy",
        "InitiatedOnART": 1/0, (Passing this 0 and not passing ARTCentreDate and InitiatedDate does not work)
        "InitiatedDate": "dd/mm/yyyy",
        "Source": "nikshay-id",
        "regby": "nikshay-user",
        "MORemark": "This is dev test", (Optional)
        "IP_FROM": "Servers IP address or Mobile device MAC Address",
        """
        episode_case = get_open_episode_case_from_person(person_case.domain, person_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()
        properties_dict = {
            "PatientID": episode_case_properties.get('nikshay_id'),
            "HIVStatus": hiv_status.get(person_case_properties.get('hiv_status')),
            "HIVTestDate": datetime.datetime.strptime(person_case_properties.get('hiv_test_date'),
                                                      '%Y-%m-%d').strftime('%d/%m/%Y'),
            # might not be available if cpt_initiated is no
            "CPTDeliverDate": datetime.datetime.strptime(
                person_case_properties.get('cpt_initiation_date', NIKSHAY_NULL_DATE), '%Y-%m-%d'
            ).strftime('%d/%m/%Y'),
            "ARTCentreDate": datetime.datetime.strptime(
                person_case_properties.get('art_initiation_date', NIKSHAY_NULL_DATE), '%Y-%m-%d'
            ).strftime('%d/%m/%Y'),
            "InitiatedOnART": art_initiated.get(person_case_properties.get('art_initiated', 'no')),
            # might not be available if art_initiated is no
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
                "nikshay_error": "",
            },
        )

    def handle_failure(self, response, payload_doc, repeat_record):
        _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()),
                            "hiv_nikshay_registered", "hiv_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, unicode(exception),
                                "hiv_nikshay_registered", "hiv_nikshay_error")


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
