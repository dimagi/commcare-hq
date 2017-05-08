import json
import datetime
import socket

from django.conf import settings

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
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
)
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_person_locations,
    get_open_episode_case_from_person,
    get_occurrence_case_from_test,
    get_open_episode_case_from_occurrence,
    get_person_case_from_occurrence,
    get_lab_referral_from_test)
from custom.enikshay.integrations.nikshay.repeaters import (
    NikshayRegisterPatientRepeater,
    NikshayHIVTestRepeater,
    NikshayTreatmentOutcomeRepeater,
    NikshayFollowupRepeater,
    NikshayRegisterPrivatePatientRepeater,
)
from custom.enikshay.integrations.nikshay.exceptions import NikshayResponseException
from custom.enikshay.exceptions import (
    NikshayLocationNotFound,
    NikshayRequiredValueMissing,
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
    treatment_outcome,
    hiv_status,
    art_initiated,
    purpose_of_testing,
    smear_result_grade,
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


@RegisterGenerator(NikshayRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class NikshayRegisterPatientPayloadGenerator(BaseNikshayPayloadGenerator):
    def get_payload(self, repeat_record, episode_case):
        """
        https://docs.google.com/document/d/1yUWf3ynHRODyVVmMrhv5fDhaK_ufZSY7y0h9ke5rBxU/edit#heading=h.a9uhx3ql595c
        """
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()

        properties_dict = self._base_properties(repeat_record)
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

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(repeat_record.domain, repeat_record.payload_id, {"nikshay_error": unicode(exception)})


@RegisterGenerator(NikshayTreatmentOutcomeRepeater, 'case_json', 'JSON', is_default=True)
class NikshayTreatmentOutcomePayload(BaseNikshayPayloadGenerator):

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
        _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()),
                            "treatment_outcome_nikshay_registered", "treatment_outcome_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, unicode(exception),
                                "treatment_outcome_nikshay_registered", "treatment_outcome_nikshay_error")


@RegisterGenerator(NikshayHIVTestRepeater, 'case_json', 'JSON', is_default=True)
class NikshayHIVTestPayloadGenerator(BaseNikshayPayloadGenerator):
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
            "HIVStatus": hiv_status.get(person_case_properties.get('hiv_status')),
            "HIVTestDate": _format_date(person_case_properties, 'hiv_test_date'),
            "CPTDeliverDate": _format_date(person_case_properties, 'cpt_1_date'),
            "ARTCentreDate": _format_date(person_case_properties, 'art_initiation_date'),
            "InitiatedOnART": art_initiated.get(
                person_case_properties.get('art_initiated', 'no'), art_initiated['no']),
            "InitiatedDate": _format_date(person_case_properties, 'art_initiation_date'),
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
        _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()),
                            "hiv_test_nikshay_registered", "hiv_test_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, unicode(exception),
                                "hiv_test_nikshay_registered", "hiv_test_nikshay_error")


@RegisterGenerator(NikshayFollowupRepeater, 'case_json', 'JSON', is_default=True)
class NikshayFollowupPayloadGenerator(BaseNikshayPayloadGenerator):
    def get_payload(self, repeat_record, test_case):
        occurence_case = get_occurrence_case_from_test(test_case.domain, test_case.get_id)
        episode_case = get_open_episode_case_from_occurrence(test_case.domain, occurence_case.get_id)
        person_case = get_person_case_from_occurrence(test_case.domain, occurence_case.get_id)

        test_case_properties = test_case.dynamic_case_properties()
        episode_case_properties = episode_case.dynamic_case_properties()

        interval_id, lab_serial_number, result_grade, dmc_code = self._get_mandatory_fields(
            test_case, test_case_properties)

        test_reported_on = _format_date(test_case_properties, 'date_reported')
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

    def _get_mandatory_fields(self, test_case, test_case_properties):
        # list of fields that we want the case to have and should raise an exception if its missing or not in
        # expected state to highlight missing essentials in repeat records. Check added here instead of
        # allow_to_forward to bring to notice these records instead of silently ignoring them
        interval_id = self._get_interval_id(test_case_properties.get('purpose_of_testing'),
                                            test_case_properties.get('follow_up_test_reason'))

        dmc_code = self._get_dmc_code(test_case, test_case_properties)
        lab_serial_number = test_case_properties.get('lab_serial_number')
        test_result_grade = test_case_properties.get('result_grade')
        bacilli_count = test_case_properties.get('max_bacilli_count')
        result_grade = self.get_result_grade(test_result_grade, bacilli_count)

        if not (lab_serial_number and result_grade):
            raise NikshayRequiredValueMissing("Mandatory value missing in one of the following "
                                       "LabSerialNo: {lab_serial_number}, ResultGrade: {result_grade}"
                                       .format(lab_serial_number=lab_serial_number,
                                               result_grade=test_result_grade))

        return interval_id, lab_serial_number, result_grade, dmc_code

    def get_result_grade(self, test_result_grade, bacilli_count):
        if test_result_grade in smear_result_grade.keys():
            return smear_result_grade.get(test_result_grade)
        elif test_result_grade == 'scanty':
            return smear_result_grade.get("SC-{b_count}".format(b_count=bacilli_count), None)

    def _get_interval_id(self, testing_purpose, follow_up_test_reason):
        if testing_purpose == 'diagnostic':
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
        if not nikshay_code or (isinstance(nikshay_code, basestring) and not nikshay_code.isdigit()):
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
        _save_error_message(payload_doc.domain, payload_doc.case_id, unicode(response.json()),
                            "followup_nikshay_registered", "followup_nikshay_error")

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            _save_error_message(repeat_record.domain, repeat_record.payload_id, unicode(exception),
                                "followup_nikshay_registered", "followup_nikshay_error")


@RegisterGenerator(NikshayRegisterPrivatePatientRepeater, 'case_xml', 'XML', is_default=True)
class NikshayRegisterPrivatePatientPayloadGenerator(BaseNikshayPayloadGenerator):
    def get_payload(self, repeat_record, episode_case):
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case_properties = person_case.dynamic_case_properties()

        person_locations = get_person_locations(person_case)
        tu_choice = person_case_properties.get('tu_choice')
        try:
            tu_location = SQLLocation.objects.get(location_id=tu_choice)
        except SQLLocation.DoesNotExist:
            raise NikshayLocationNotFound(
                "Location with id {location_id} not found. This is the tu_choide for person with id: {person_id}"
                .format(location_id=tu_choice, person_id=person_case.case_id)
            )
        try:
            tu_code = tu_location.metadata['nikshay_code']
        except (KeyError, AttributeError) as e:
            raise NikshayCodeNotFound("Nikshay codes not found for location with id: {}: {}"
                                      .format(tu_location.get_id, e))
        episode_case_date = episode_case_properties.get('date_of_diagnosis', None)
        if episode_case_date:
            episode_date = datetime.datetime.strptime(episode_case_date, "%Y-%m-%d").date()
        else:
            episode_date = datetime.date.today()

        return {
            "Stocode": person_locations.sto,
            "Dtocode": person_locations.dto,
            "TBUcode": tu_code,
            "HFIDNO": person_locations.phi,
            "pname": person_case.name,
            "fhname": person_case_properties.get('husband_father_name', ''),
            "age": person_case_properties.get('age', ''),
            "gender": person_case_properties.get('sex', '').capitalize(),
            "Address": person_case_properties.get('current_address', ''),
            "pin": person_case_properties.get('current_address_postal_code', ''),
            "lno": person_case_properties.get('phone', ''),
            "mno": '0',
            "tbdiagdate": str(episode_date),
            "tbstdate": episode_case_properties.get(TREATMENT_START_DATE, str(datetime.date.today())),
            "Type": disease_classification.get(episode_case_properties.get('pulmonary_extra_pulmonary', ''), ''),
            "B_diagnosis": episode_case_properties.get('case_definition', ''),
            "D_SUSTest": episode_case_properties.get('drug_susceptibility_test_status', ''),
            "Treat_I": episode_case_properties.get('treatment_initiation_status', ''),
            "usersid": settings.ENIKSHAY_PRIVATE_API_USERS.get(person_locations.sto, ''),
            "password": settings.ENIKSHAY_PRIVATE_API_PASSWORD,
            "source": ENIKSHAY_ID,
        }

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

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(repeat_record.domain, repeat_record.payload_id, {"nikshay_error": unicode(exception)})


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


def _format_date(case_properties, case_property):
    date = case_properties.get(case_property) or NIKSHAY_NULL_DATE
    try:
        return datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return datetime.datetime.strptime(NIKSHAY_NULL_DATE, '%Y-%m-%d').strftime('%d/%m/%Y')
