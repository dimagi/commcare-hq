from __future__ import absolute_import
import re
import json
import datetime
import socket
from django.conf import settings

from corehq.apps.locations.models import SQLLocation
from custom.enikshay.integrations.bets.repeater_generators import LocationPayloadGenerator
from corehq.motech.repeaters.exceptions import RequestConnectionError
from corehq.motech.repeaters.repeater_generators import BasePayloadGenerator, SOAPPayloadGeneratorMixin
from custom.enikshay.const import (
    PRIMARY_PHONE_NUMBER,
    BACKUP_PHONE_NUMBER,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    TREATMENT_SUPPORTER_PHONE,
    TREATMENT_START_DATE,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
    DSTB_EPISODE_TYPE,
    PERSON_CASE_2B_VERSION,
    HEALTH_ESTABLISHMENT_SUCCESS_RESPONSE_REGEX,
    NOT_AVAILABLE_VALUE,
    DUMMY_VALUES,
    AGENCY_LOCATION_TYPES,
)
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_person_locations,
    get_open_episode_case_from_person,
    get_occurrence_case_from_test,
    get_associated_episode_case_for_test,
    get_person_case_from_occurrence,
    get_lab_referral_from_test,
    get_occurrence_case_from_episode,
)
from custom.enikshay.integrations.nikshay.exceptions import (
    NikshayResponseException,
)
from custom.enikshay.exceptions import (
    NikshayLocationNotFound,
    NikshayRequiredValueMissing,
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
    treatment_outcome,
    hiv_status,
    art_initiated,
    purpose_of_testing,
    smear_result_grade,
    drug_susceptibility_test_status,
    basis_of_diagnosis,
    health_establishment_type,
    health_establishment_sector,
)
from custom.enikshay.case_utils import update_case
from dimagi.utils.post import parse_SOAP_response

from custom.enikshay.integrations.nikshay.utils import get_location_user_for_notification
from custom.enikshay.location_utils import get_health_establishment_hierarchy_codes
from dimagi.utils.decorators.memoized import memoized
import six

ENIKSHAY_ID = 8
NIKSHAY_NULL_DATE = '1900-01-01'

# to accept only alphanumberic, ignore any encoded text \u0000, non-word & _
SOAP_RESTRICTED_TEXT_REGEX = r'(\\u[a-zA-Z0-9]{4}|\W|_)'


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

    def _base_properties(self, repeat_record):
        username, password = self._get_credentials(repeat_record)
        server_ip = socket.gethostbyname(socket.gethostname())
        return {
            "regBy": username,
            "regby": username,
            "RegBy": username,
            "password": password,
            "Source": ENIKSHAY_ID,
            "IP_From": server_ip,
            "IP_FROM": server_ip,
        }

    @staticmethod
    def use_2b_app_structure(person_case):
        return person_case.dynamic_case_properties().get('case_version') == PERSON_CASE_2B_VERSION


class NikshayRegisterPatientPayloadGenerator(BaseNikshayPayloadGenerator):
    deprecated_format_names = ('case_json',)

    def get_payload(self, repeat_record, episode_case):
        """
        https://docs.google.com/document/d/1yUWf3ynHRODyVVmMrhv5fDhaK_ufZSY7y0h9ke5rBxU/edit#heading=h.a9uhx3ql595c
        """
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()
        occurence_case = None
        use_2b_app_structure = self.use_2b_app_structure(person_case)
        if use_2b_app_structure:
            occurence_case = get_occurrence_case_from_episode(episode_case.domain, episode_case.get_id)
        properties_dict = self._base_properties(repeat_record)
        properties_dict.update({
            "dotcenter": "NA",
            "Local_ID": person_case.get_id,
        })

        try:
            properties_dict.update(_get_person_case_properties(
                episode_case, person_case, person_case_properties))
        except NikshayLocationNotFound as e:
            _save_error_message(person_case.domain, person_case.case_id, e)
        properties_dict.update(_get_episode_case_properties(
            episode_case_properties, occurence_case, person_case, use_2b_app_structure))
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
            _save_error_message(payload_doc.domain, payload_doc.case_id, six.text_type(e.message))

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
            _save_error_message(payload_doc.domain, payload_doc.case_id, six.text_type(response.json()))

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(repeat_record.domain, repeat_record.payload_id, {"nikshay_error": six.text_type(exception)})


class NikshayTreatmentOutcomePayload(BaseNikshayPayloadGenerator):
    deprecated_format_names = ('case_json',)

    def get_payload(self, repeat_record, episode_case):
        """
        https://docs.google.com/document/d/1yUWf3ynHRODyVVmMrhv5fDhaK_ufZSY7y0h9ke5rBxU/edit#heading=h.6zwqb0ms7iz9
        """
        episode_case_properties = episode_case.dynamic_case_properties()
        base_properties = self._base_properties(repeat_record)
        base_properties.update({
            "PatientID": episode_case_properties.get("nikshay_id"),
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
        _save_error_message(payload_doc.domain, payload_doc.case_id, six.text_type(response.json()),
                            "treatment_outcome_nikshay_registered", "treatment_outcome_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, six.text_type(exception),
                                "treatment_outcome_nikshay_registered", "treatment_outcome_nikshay_error")


class NikshayHIVTestPayloadGenerator(BaseNikshayPayloadGenerator):
    deprecated_format_names = ('case_json',)

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
        base_properties = self._base_properties(repeat_record)
        base_properties.update({
            "PatientID": episode_case_properties.get('nikshay_id'),
            "HIVStatus": hiv_status.get(person_case_properties.get('hiv_status'), hiv_status.get('unknown')),
            "HIVTestDate": _format_date_or_null_date(person_case_properties, 'hiv_test_date'),
            "CPTDeliverDate": _format_date_or_null_date(person_case_properties, 'cpt_1_date'),
            "ARTCentreDate": _format_date_or_null_date(person_case_properties, 'art_initiation_date'),
            "InitiatedOnART": art_initiated.get(
                person_case_properties.get('art_initiated', 'no'), art_initiated['no']),
            "InitiatedDate": _format_date_or_null_date(person_case_properties, 'art_initiation_date'),
        })

        return json.dumps(base_properties)

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
        _save_error_message(payload_doc.domain, payload_doc.case_id, six.text_type(response.json()),
                            "hiv_test_nikshay_registered", "hiv_test_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, six.text_type(exception),
                                "hiv_test_nikshay_registered", "hiv_test_nikshay_error")


class NikshayFollowupPayloadGenerator(BaseNikshayPayloadGenerator):
    deprecated_format_names = ('case_json',)

    def get_payload(self, repeat_record, test_case):
        occurence_case = get_occurrence_case_from_test(test_case.domain, test_case.get_id)
        episode_case = get_associated_episode_case_for_test(test_case, occurence_case.get_id)
        person_case = get_person_case_from_occurrence(test_case.domain, occurence_case.get_id)

        test_case_properties = test_case.dynamic_case_properties()
        episode_case_properties = episode_case.dynamic_case_properties()
        use_2b_app_structure = self.use_2b_app_structure(person_case)

        interval_id, lab_serial_number, result_grade, dmc_code = self._get_mandatory_fields(
            test_case, test_case_properties, occurence_case,
            use_2b_app_structure
        )

        test_reported_on = _format_date_or_null_date(test_case_properties, 'date_reported')
        properties_dict = self._base_properties(repeat_record)
        properties_dict.update({
            "PatientID": episode_case_properties.get('nikshay_id'),
            "TestDate": test_reported_on,
            "LabNo": lab_serial_number,
            "Local_ID": person_case.get_id,
            "IntervalId": interval_id,
            # since weight is not taken and is mandatory we send 1
            "PatientWeight": test_case_properties.get('weight', 1),
            "SmearResult": result_grade,
            "DMC": dmc_code
        })

        return json.dumps(properties_dict)

    def _get_mandatory_fields(self, test_case, test_case_properties, occurence_case, use_2b_app_structure):
        # list of fields that we want the case to have and should raise an exception if its missing or not in
        # expected state to highlight missing essentials in repeat records. Check added here instead of
        # allow_to_forward to bring to notice these records instead of silently ignoring them
        interval_id = self._get_interval_id(
            test_case_properties, use_2b_app_structure
        )

        dmc_code = self._get_dmc_code(test_case, test_case_properties)
        lab_serial_number = test_case_properties.get('lab_serial_number')
        test_result_grade = test_case_properties.get('result_grade')
        bacilli_count = test_case_properties.get('max_bacilli_count')
        try:
            # Since 9 is the max value supported by Nikshay, notify 9 in case 9+
            if bacilli_count and int(bacilli_count) > 9:
                bacilli_count = '9'
        except ValueError:
            pass
        result_grade = self.get_result_grade(test_result_grade, bacilli_count)

        if not (lab_serial_number and result_grade):
            raise NikshayRequiredValueMissing("Mandatory value missing in one of the following "
                                              "LabSerialNo: {lab_serial_number}, ResultGrade: {result_grade}, "
                                              "Max Bacilli Count: {max_bacilli_count}"
                                              .format(lab_serial_number=lab_serial_number,
                                                      result_grade=test_result_grade,
                                                      max_bacilli_count=bacilli_count))

        return interval_id, lab_serial_number, result_grade, dmc_code

    def get_result_grade(self, test_result_grade, bacilli_count):
        if test_result_grade in smear_result_grade:
            return smear_result_grade.get(test_result_grade)
        elif test_result_grade == 'scanty':
            return smear_result_grade.get("SC-{b_count}".format(b_count=bacilli_count), None)

    def _get_interval_id(self, test_case_properties, use_2b_app_structure):
        if use_2b_app_structure:
            testing_purpose = test_case_properties.get('rft_general')
            follow_up_test_reason = test_case_properties.get('rft_dstb_followup')
        else:
            testing_purpose = test_case_properties.get('purpose_of_testing')
            follow_up_test_reason = test_case_properties.get('follow_up_test_reason')
        if testing_purpose in ['diagnostic', 'diagnosis_dstb', 'diagnosis_drtb']:
            interval_id = 0
        else:
            interval_id = purpose_of_testing.get(follow_up_test_reason, None)
        if interval_id is None:
            raise NikshayRequiredValueMissing(
                "Value missing for intervalID, purpose_of_testing: {testing_purpose}, "
                "follow_up_test_reason: {follow_up_test_reason}".format(
                    testing_purpose=testing_purpose, follow_up_test_reason=follow_up_test_reason)
            )
        return interval_id

    def _get_dmc_code(self, test_case, test_case_properties):
        dmc_location_id = test_case_properties.get("testing_facility_id", None)
        if not dmc_location_id:
            # fallback to lab referral case owner id for older versions of app
            lab_referral_case = get_lab_referral_from_test(test_case.domain, test_case.get_id)
            dmc_location_id = lab_referral_case.owner_id
        if not dmc_location_id:
            raise NikshayRequiredValueMissing("Value missing for dmc_code/testing_facility_id for test case: " +
                                              test_case.get_id)
        dmc = SQLLocation.active_objects.get_or_None(location_id=dmc_location_id)
        if not dmc:
            raise NikshayLocationNotFound(
                "Location with id: {location_id} not found."
                "This is the testing facility id assigned for test: {test_case_id}".format(
                    location_id=dmc_location_id, test_case_id=test_case.get_id)
            )
        nikshay_code = dmc.metadata.get('nikshay_code')
        if not nikshay_code or (isinstance(nikshay_code, six.string_types) and not nikshay_code.isdigit()):
            raise NikshayRequiredValueMissing("Inappropriate value for dmc, got value: {}".format(nikshay_code))
        return dmc.metadata.get('nikshay_code')

    def handle_success(self, response, payload_doc, repeat_record):
        update_case(
            payload_doc.domain,
            payload_doc.case_id,
            {
                "followup_nikshay_registered": "true",
                "followup_nikshay_error": "",
            },
        )

    def handle_failure(self, response, payload_doc, repeat_record):
        _save_error_message(payload_doc.domain, payload_doc.case_id, six.text_type(response.json()),
                            "followup_nikshay_registered", "followup_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, six.text_type(exception),
                                "followup_nikshay_registered", "followup_nikshay_error")


class NikshayRegisterPrivatePatientPayloadGenerator(SOAPPayloadGeneratorMixin, BaseNikshayPayloadGenerator):
    format_name = 'case_xml'
    format_label = 'XML'

    @memoized
    def _get_person_locations(self, episode_case):
        person_case = self._get_person_case(episode_case)
        return get_person_locations(person_case)

    @memoized
    def _get_person_case(self, episode_case):
        return get_person_case_from_episode(episode_case.domain, episode_case.get_id)

    def get_payload(self, repeat_record, episode_case):
        person_case = self._get_person_case(episode_case)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()

        person_locations = self._get_person_locations(episode_case)
        episode_case_date = episode_case_properties.get('date_of_diagnosis', None)
        if episode_case_date:
            episode_date = datetime.datetime.strptime(episode_case_date, "%Y-%m-%d").date()
        else:
            episode_date = datetime.date.today()
        return {
            "Stocode": person_locations.sto,
            "Dtocode": person_locations.dto,
            "TBUcode": person_locations.tu,
            "HFIDNO": person_locations.pcp,
            "pname": sanitize_text_for_xml(person_case.name),
            "fhname": sanitize_text_for_xml(person_case_properties.get('husband_father_name', '')),
            "age": _get_person_age(person_case_properties),
            "gender": person_case_properties.get('sex', '').capitalize(),
            # API for Address with char ',' returns Invalid data format error
            "Address": sanitize_text_for_xml(person_case_properties.get('current_address', '').replace(',', '')),
            "pin": person_case_properties.get('current_address_postal_code', ''),
            "lno": person_case_properties.get('phone_number', ''),
            "mno": '0',
            "tbdiagdate": _format_date(str(episode_date)),
            "tbstdate": _format_date(
                episode_case_properties.get(TREATMENT_START_DATE, str(datetime.date.today()))),
            "Type": disease_classification.get(episode_case_properties.get('disease_classification', ''), ''),
            "B_diagnosis": basis_of_diagnosis.get(episode_case_properties.get('basis_of_diagnosis', ''), ''),
            "D_SUSTest": drug_susceptibility_test_status.get(episode_case_properties.get('dst_status', '')),
            "Treat_I": episode_case_properties.get('treatment_initiation_status', ''),
            "usersid": settings.ENIKSHAY_PRIVATE_API_USERS.get(person_locations.sto, ''),
            "password": settings.ENIKSHAY_PRIVATE_API_PASSWORD,
            "Source": ENIKSHAY_ID,
        }

    def handle_success(self, response, payload_doc, repeat_record):
        message = parse_SOAP_response(
            repeat_record.repeater.url,
            repeat_record.repeater.operation,
            response,
            verify=repeat_record.repeater.verify,
        )
        try:
            health_facility_id = self._get_person_locations(payload_doc).pcp
        except NikshayLocationNotFound as e:
            self.handle_exception(e, repeat_record)
        else:
            nikshay_id = '-'.join([health_facility_id, message])
            update_case(
                payload_doc.domain,
                payload_doc.case_id,
                {
                    "private_nikshay_registered": "true",
                    "nikshay_id": nikshay_id,
                    "private_nikshay_error": "",
                    "date_private_nikshay_notification": datetime.date.today(),
                },
                external_id=nikshay_id,
            )

    def handle_failure(self, response, payload_doc, repeat_record):
        message = parse_SOAP_response(
            repeat_record.repeater.url,
            repeat_record.repeater.operation,
            response,
            verify=repeat_record.repeater.verify,
        )
        _save_error_message(payload_doc.domain, payload_doc.case_id, six.text_type(message),
                            "private_nikshay_registered", "private_nikshay_error"
                            )

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(
                repeat_record.domain,
                repeat_record.payload_id,
                {
                    "private_nikshay_error": six.text_type(exception)
                }
            )


class NikshayHealthEstablishmentPayloadGenerator(SOAPPayloadGeneratorMixin, LocationPayloadGenerator):
    format_name = 'location_xml'
    format_label = 'XML'

    @staticmethod
    def _get_establishment_type(location):
        if location.location_type.name == AGENCY_LOCATION_TYPES['plc']:
            return health_establishment_type.get('lab')
        if location.location_type.name == AGENCY_LOCATION_TYPES['pcp']:
            return health_establishment_type.get(
                location.metadata.get('facility_type')
            )

    @staticmethod
    def _get_address(location_user_data):
        if location_user_data.get('address_line_1') or location_user_data.get('address_line_2'):
            return (u"%s %s" % (
                location_user_data.get('address_line_1'), location_user_data.get('address_line_2'))).strip()
        else:
            return NOT_AVAILABLE_VALUE

    @staticmethod
    def _get_mobile_number(location_user_data):
        contact_phone_number = location_user_data.get('contact_phone_number')
        if contact_phone_number:
            # reject any isd codes entered like 919876543210 so pick last 10 digits only
            return contact_phone_number.strip()[-10:]
        return DUMMY_VALUES['phone_number']

    @staticmethod
    def _get_telephone_number(location_user_data):
        landline_no = location_user_data.get('landline_no')
        if landline_no:
            # reject any isd codes entered like 02223777800 so pick last 10 digits only
            return landline_no.strip()[-10:]
        return DUMMY_VALUES['phone_number']

    @staticmethod
    def _get_value_or_dummy_value(location_user_data, value_for):
        return location_user_data.get(value_for) or DUMMY_VALUES.get(value_for)

    def get_payload(self, repeat_record, location):
        location_hierarchy_codes = get_health_establishment_hierarchy_codes(location)
        location_user = get_location_user_for_notification(location)
        location_user_data = location_user.user_data
        return {
            'ESTABLISHMENT_TYPE': self._get_establishment_type(location),
            'SECTOR': health_establishment_sector.get(location.metadata.get('sector', ''), ''),
            'ESTABLISHMENT_NAME': location.name,
            'MCI_HR_NO': self._get_value_or_dummy_value(location_user_data, 'registration_number'),
            'CONTACT_PNAME': location_user.full_name,
            'CONTACT_PDESIGNATION': (location_user_data.get('pcp_qualification') or NOT_AVAILABLE_VALUE),
            'TELEPHONE_NO': self._get_telephone_number(location_user_data),
            'MOBILE_NO': self._get_mobile_number(location_user_data),
            'COMPLETE_ADDRESS': self._get_address(location_user_data),
            'PINCODE': self._get_value_or_dummy_value(location_user_data, 'pincode'),
            'EMAILID': self._get_value_or_dummy_value(location_user_data, 'email'),
            'STATE_CODE': location_hierarchy_codes.stcode,
            'DISTRICT_CODE': location_hierarchy_codes.dtcode,
            'TBU_CODE': location.metadata.get('nikshay_tu_id'),
            'MUST_CREATE_NEW': 'N',
            'USER_ID': settings.ENIKSHAY_PRIVATE_API_USERS.get(location_hierarchy_codes.stcode, ''),
            'PASSWORD': settings.ENIKSHAY_PRIVATE_API_PASSWORD,
            'Source': ENIKSHAY_ID,
        }

    def handle_success(self, response, payload_doc, repeat_record):
        message = parse_SOAP_response(
            repeat_record.repeater.url,
            repeat_record.repeater.operation,
            response,
            verify=repeat_record.repeater.verify,
        )
        message_text = message.find("NewDataSet/HE_DETAILS/Message").text
        health_facility_id = re.match(HEALTH_ESTABLISHMENT_SUCCESS_RESPONSE_REGEX, message_text).groups()[0]
        if payload_doc.metadata.get('nikshay_code'):
            # The repeater checks for this to be absent but in case its added after the trigger
            # and before its fetched from Nikshay, just keep a copy of the older value for ref
            payload_doc.metadata['old_nikshay_code'] = payload_doc.metadata.get('nikshay_code')
        payload_doc.metadata['nikshay_code'] = health_facility_id
        payload_doc.save()


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


def _get_person_age(person_case_properties):
    # Nikshay excepts only integer value so pick floor value or 1 in case age less than 1
    # 2.3 => 2, 0.5 => 1
    person_age = person_case_properties.get('age', '') or person_case_properties.get('age_entered', '')
    person_age = person_age.split('.')[0]
    if person_age == '0':
        person_age = '1'
    return person_age


def _get_person_case_properties(episode_case, person_case, person_case_properties):
    """
    :return: Example {'dcode': u'JLR', 'paddress': u'123, near asdf, Jalore, Rajasthan ', 'cmob': u'1234567890',
    'pname': u'home visit', 'scode': u'RJ', 'tcode': 'AB', dotphi': u'Test S1-C1-D1-T1 PHI 1',
    'pmob': u'1234567890', 'cname': u'123', 'caddress': u'123', 'pgender': 'T', 'page': u'79', 'pcategory': 1}
    """
    person_category = '2' if person_case_properties.get('previous_tb_treatment', '') == 'yes' else '1'
    person_properties = {
        "pname": person_case.name,
        "pgender": gender_mapping.get(person_case_properties.get('sex', ''), ''),
        # 2B is currently setting age_entered but we are in the short term moving it to use age instead
        "page": _get_person_age(person_case_properties),
        "paddress": person_case_properties.get('current_address', ''),
        # send 0 since that is accepted by Nikshay for this mandatory field
        "pmob": (person_case_properties.get(PRIMARY_PHONE_NUMBER) or '0'),
        "cname": person_case_properties.get('secondary_contact_name_address', ''),
        "caddress": person_case_properties.get('secondary_contact_name_address', ''),
        "cmob": person_case_properties.get(BACKUP_PHONE_NUMBER, ''),
        "pcategory": person_category
    }
    person_locations = get_person_locations(person_case, episode_case)
    person_properties.update(
        {
            'scode': person_locations.sto,
            'dcode': person_locations.dto,
            'tcode': person_locations.tu,
            'dotphi': person_locations.phi,
        }
    )

    return person_properties


def _get_episode_case_properties(episode_case_properties, occurence_case, person_case, use_new_2b_structure):
    """
    :return: Example : {'dateofInitiation': '2016-12-01', 'pregdate': '2016-12-01', 'dotdesignation': u'tbhv_to',
    'ptbyr': '2016', 'dotpType': '7', 'dotmob': u'1234567890', 'dotname': u'asdfasdf', 'Ptype': '1',
    'poccupation': 1, 'disease_classification': 'P', 'sitedetail: 1}
    """
    episode_properties = {}

    if use_new_2b_structure:
        occurence_case_properties = occurence_case.dynamic_case_properties()
        episode_site_choice = occurence_case_properties.get('site_choice')
        patient_occupation = person_case.dynamic_case_properties().get('occupation', 'other')
        episode_disease_classification = occurence_case_properties.get('disease_classification', '')
    else:
        episode_site_choice = episode_case_properties.get('site_choice')
        patient_occupation = episode_case_properties.get('occupation', 'other')
        episode_disease_classification = episode_case_properties.get('disease_classification', '')

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
            patient_occupation,
            occupation['other']
        ),
        "pregdate": str(episode_date),
        "ptbyr": str(episode_year),
        "disease_classification": disease_classification.get(
            episode_disease_classification,
            ''
        ),
        "dcpulmunory": dcpulmonory.get(episode_disease_classification, "N"),
        "dcexpulmunory": dcexpulmonory.get(episode_disease_classification, "N"),
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
            error_field: six.text_type(error),
        },
    )


def _format_date_or_null_date(case_properties, case_property):
    date = case_properties.get(case_property) or NIKSHAY_NULL_DATE
    try:
        return _format_date(date)
    except ValueError:
        return _format_date(NIKSHAY_NULL_DATE)


def _format_date(date):
    return datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')


def sanitize_text_for_xml(text):
    # little hack to end up with proper spacing for valid text
    # convert all restricted chars to * and then convert any group of *s to an empty space
    return re.sub(
        r'(\*+)',
        ' ',
        re.sub(SOAP_RESTRICTED_TEXT_REGEX, '*', text)
    ).strip()
