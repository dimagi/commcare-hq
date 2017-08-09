import json

import jsonobject
from datetime import datetime, date

import pytz
from pytz import timezone

from django.core.serializers.json import DjangoJSONEncoder
from corehq.util.soft_assert import soft_assert
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.motech.repeaters.exceptions import RequestConnectionError
from corehq.motech.repeaters.repeater_generators import (
    BasePayloadGenerator, LocationPayloadGenerator, UserPayloadGenerator)
from custom.enikshay.case_utils import update_case, get_person_case_from_episode
from custom.enikshay.const import (
    DATE_FULFILLED,
    FULFILLED_BY_ID,
    FULFILLED_BY_LOCATION_ID,
    AMOUNT_APPROVED,
    TREATMENT_OUTCOME_DATE,
    PRESCRIPTION_TOTAL_DAYS_THRESHOLD,
    LAST_VOUCHER_CREATED_BY_ID,
    NOTIFYING_PROVIDER_USER_ID,
    INVESTIGATION_TYPE,
    USERTYPE_DISPLAYS,
)
from custom.enikshay.integrations.bets.const import (
    TREATMENT_180_EVENT,
    DRUG_REFILL_EVENT,
    SUCCESSFUL_TREATMENT_EVENT,
    DIAGNOSIS_AND_NOTIFICATION_EVENT,
    AYUSH_REFERRAL_EVENT,
    LOCATION_TYPE_MAP,
    CHEMIST_VOUCHER_EVENT, LAB_VOUCHER_EVENT, TOTAL_DAY_THRESHOLDS)
from custom.enikshay.exceptions import NikshayLocationNotFound
from .utils import get_bets_location_json


def _get_district_location(pcp_location):
    try:
        district_location = pcp_location.parent
        if district_location.location_type.code != 'dto':
            raise NikshayLocationNotFound("Parent location of {} is not a district".format(pcp_location))
        return pcp_location.parent.location_id
    except AttributeError:
        raise NikshayLocationNotFound("Parent location of {} not found".format(pcp_location))


class BETSPayload(jsonobject.JsonObject):

    EventID = jsonobject.StringProperty(required=True)
    EventOccurDate = jsonobject.StringProperty(required=True)
    BeneficiaryUUID = jsonobject.StringProperty(required=True)
    BeneficiaryType = jsonobject.StringProperty(required=True)
    Location = jsonobject.StringProperty(required=True)
    DTOLocation = jsonobject.StringProperty(required=True)

    @classmethod
    def _get_location(cls, location_id, field_name=None, related_case_type=None, related_case_id=None):
        try:
            return SQLLocation.objects.get(location_id=location_id)
        except SQLLocation.DoesNotExist:
            msg = "Location with id {location_id} not found.".format(location_id=location_id)
            if field_name and related_case_type and related_case_id:
                msg += " This is the {field_name} for {related_case_type} with id: {related_case_id}".format(
                    field_name=field_name,
                    related_case_type=related_case_type,
                    related_case_id=related_case_id,
                )
            raise NikshayLocationNotFound(msg)


class IncentivePayload(BETSPayload):
    EpisodeID = jsonobject.StringProperty(required=False)

    @classmethod
    def create_180_treatment_payload(cls, episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)
        pcp_location = cls._get_location(
            person_case.owner_id,
            field_name="owner_id",
            related_case_type="person",
            related_case_id=person_case.case_id
        )

        treatment_outcome_date = episode_case_properties.get(TREATMENT_OUTCOME_DATE, None)
        if treatment_outcome_date is None:
            treatment_outcome_date = datetime.utcnow().strftime("%Y-%m-%d")

        return cls(
            EventID=TREATMENT_180_EVENT,
            EventOccurDate=treatment_outcome_date,
            BeneficiaryUUID=episode_case_properties.get(LAST_VOUCHER_CREATED_BY_ID),
            BeneficiaryType="mbbs",
            EpisodeID=episode_case.case_id,
            Location=person_case.owner_id,
            DTOLocation=_get_district_location(pcp_location),
        )

    @classmethod
    def create_drug_refill_payload(cls, episode_case, n):
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)
        event_date = episode_case_properties.get(PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(n))

        pcp_location = cls._get_location(
            person_case.owner_id,
            field_name="owner_id",
            related_case_type="person",
            related_case_id=person_case.case_id,
        )

        return cls(
            EventID=DRUG_REFILL_EVENT,
            EventOccurDate=event_date,
            BeneficiaryUUID=person_case.case_id,
            BeneficiaryType="patient",
            EpisodeID=episode_case.case_id,
            Location=person_case.owner_id,
            DTOLocation=_get_district_location(pcp_location)
        )

    @classmethod
    def create_successful_treatment_payload(cls, episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)

        location = cls._get_location(
            person_case.dynamic_case_properties().get('last_owner'),
            field_name="last_owner",
            related_case_type="person",
            related_case_id=person_case.case_id,
        )

        return cls(
            EventID=SUCCESSFUL_TREATMENT_EVENT,
            EventOccurDate=episode_case_properties.get(TREATMENT_OUTCOME_DATE),
            BeneficiaryUUID=person_case.case_id,
            BeneficiaryType="patient",
            EpisodeID=episode_case.case_id,
            Location=person_case.dynamic_case_properties().get('last_owner'),
            DTOLocation=_get_district_location(location),
        )

    @staticmethod
    def _india_now():
        utc_now = pytz.UTC.localize(datetime.utcnow())
        india_now = utc_now.replace(tzinfo=timezone('Asia/Kolkata')).date()
        return str(india_now)

    @classmethod
    def create_diagnosis_and_notification_payload(cls, episode_case):
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)

        location = cls._get_location(
            person_case.owner_id,
            field_name="owner_id",
            related_case_type="person",
            related_case_id=person_case.case_id,
        )

        return cls(
            EventID=DIAGNOSIS_AND_NOTIFICATION_EVENT,
            EventOccurDate=cls._india_now(),
            BeneficiaryUUID=episode_case.dynamic_case_properties().get(NOTIFYING_PROVIDER_USER_ID),
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type.code],
            EpisodeID=episode_case.case_id,
            Location=person_case.owner_id,
            DTOLocation=_get_district_location(location),
        )

    @classmethod
    def create_ayush_referral_payload(cls, episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()

        location = cls._get_location(
            episode_case_properties.get("registered_by"),
            field_name="registered_by",
            related_case_type="episode",
            related_case_id=episode_case.case_id,
        )
        if not location.user_id:
            raise NikshayLocationNotFound(
                "Location {} does not have a virtual location user".format(location.location_id))

        return cls(
            EventID=AYUSH_REFERRAL_EVENT,
            EventOccurDate=cls._india_now(),
            BeneficiaryUUID=location.user_id,
            BeneficiaryType='ayush_other',
            EpisodeID=episode_case.case_id,
            Location=episode_case_properties.get("registered_by"),
            DTOLocation=_get_district_location(location),
        )

    def payload_json(self):
        return {"incentive_details": [self.to_json()]}


class VoucherPayload(BETSPayload):

    VoucherID = jsonobject.StringProperty(required=False)
    Amount = jsonobject.StringProperty(required=False)
    EnikshayApprover = jsonobject.StringProperty(required=False)
    EnikshayRole = jsonobject.StringProperty(required=False)
    EnikshayApprovalDate = jsonobject.StringProperty(required=False)

    @classmethod
    def create_voucher_payload(cls, voucher_case):
        voucher_case_properties = voucher_case.dynamic_case_properties()
        fulfilled_by_id = voucher_case_properties.get(FULFILLED_BY_ID)
        fulfilled_by_location_id = voucher_case_properties.get(FULFILLED_BY_LOCATION_ID)
        event_id = {
            "prescription": CHEMIST_VOUCHER_EVENT,
            "test": LAB_VOUCHER_EVENT,
        }[voucher_case_properties['voucher_type']]

        location = cls._get_location(
            fulfilled_by_location_id,
            field_name=FULFILLED_BY_LOCATION_ID,
            related_case_type="voucher",
            related_case_id=voucher_case.case_id
        )

        approver_id = voucher_case.get_case_property('voucher_approved_by_id')
        if approver_id:
            approver = CommCareUser.get_by_user_id(approver_id)
            approver_name = approver.name
            usertype = approver.user_data.get('usertype')
            approver_usertype = USERTYPE_DISPLAYS.get(usertype, usertype)
        else:
            approver_name = None
            approver_usertype = None

        return cls(
            EventID=event_id,
            EventOccurDate=voucher_case_properties.get(DATE_FULFILLED),
            VoucherID=voucher_case.case_id,
            BeneficiaryUUID=fulfilled_by_id,
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type.code],
            Location=fulfilled_by_location_id,
            Amount=voucher_case_properties.get(AMOUNT_APPROVED),
            DTOLocation=_get_district_location(location),
            InvestigationType=voucher_case_properties.get(INVESTIGATION_TYPE),
            EnikshayApprover=approver_name,
            EnikshayRole=approver_usertype,
            EnikshayApprovalDate=voucher_case.get_case_property('date_approved'),
        )

    def payload_json(self):
        return {"voucher_details": [self.to_json()]}


class BETSBasePayloadGenerator(BasePayloadGenerator):
    event_id = None

    @property
    def event_property_name(self):
        return "event_{}".format(self.event_id)

    @property
    def content_type(self):
        return 'application/json'

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(repeat_record.domain, repeat_record.payload_id, {
                "bets_{}_error".format(self.event_id): u"RequestConnectionError: {}".format(unicode(exception))
            })

    def handle_success(self, response, case, repeat_record):
        update_case(
            case.domain,
            case.case_id,
            {
                self.event_property_name: "sent",
                "bets_{}_error".format(self.event_id): ""
            }
        )

    def handle_failure(self, response, case, repeat_record):
        update_case(
            case.domain,
            case.case_id,
            {
                self.event_property_name: (
                    "error"
                    if case.dynamic_case_properties().get(self.event_property_name) != 'sent'
                    else 'sent'
                ),
                "bets_{}_error".format(self.event_id): unicode(response.json()),
            }
        )


class BaseBETSVoucherPayloadGenerator(BETSBasePayloadGenerator):

    def get_test_payload(self, domain):
        return json.dumps(VoucherPayload(
            VoucherID="DUMMY-VOUCHER-ID",
            Amount="0",
            EventID="DUMMY-EVENT-ID",
            EventOccurDate="2017-01-01",
            BeneficiaryUUID="DUMMY-BENEFICIARY-ID",
            BeneficiaryType="chemist",
            location="DUMMY-LOCATION",
        ).payload_json())

    def get_payload(self, repeat_record, voucher_case):
        return json.dumps(VoucherPayload.create_voucher_payload(voucher_case).payload_json())


class ChemistBETSVoucherPayloadGenerator(BaseBETSVoucherPayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = CHEMIST_VOUCHER_EVENT


class LabBETSVoucherPayloadGenerator(BaseBETSVoucherPayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = LAB_VOUCHER_EVENT


class IncentivePayloadGenerator(BETSBasePayloadGenerator):

    def get_test_payload(self, domain):
        return json.dumps(IncentivePayload(
            EpisodeID="DUMMY-EPISODE-ID",
            EventID="DUMMY-EVENT-ID",
            EventOccurDate="2017-01-01",
            BeneficiaryUUID="DUMMY-BENEFICIARY-ID",
            BeneficiaryType="chemist",
            Location="DUMMY-LOCATION",
            DTOLocation="DUMMY-LOCATION",
        ).payload_json())


class BETS180TreatmentPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = TREATMENT_180_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_180_treatment_payload(episode_case).payload_json())


class BETSDrugRefillPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = DRUG_REFILL_EVENT

    @staticmethod
    def _get_prescription_threshold_to_send(episode_case):
        from custom.enikshay.integrations.bets.repeaters import BETSDrugRefillRepeater
        thresholds_to_send = [
            n for n in TOTAL_DAY_THRESHOLDS
            if BETSDrugRefillRepeater.prescription_total_days_threshold_in_trigger_state(
                episode_case.dynamic_case_properties(), n
            )
        ]

        _assert = soft_assert('{}@{}.com'.format('frener', 'dimagi'))
        message = ("Repeater should not have allowed to forward if there were more or less than"
                   "one threshold to trigger. Episode case: {}".format(episode_case.case_id))
        _assert(len(thresholds_to_send) == 1, message)

        try:
            return thresholds_to_send[0]
        except IndexError:
            return 0

    def get_payload(self, repeat_record, episode_case):
        n = self._get_prescription_threshold_to_send(episode_case)
        return json.dumps(IncentivePayload.create_drug_refill_payload(episode_case, n).payload_json())

    def get_event_property_name(self, episode_case):
        n = self._get_prescription_threshold_to_send(episode_case)
        return "event_{}_{}".format(self.event_id, n)

    def handle_success(self, response, case, repeat_record):
        event_property_name = self.get_event_property_name(case)
        update_case(
            case.domain,
            case.case_id,
            {
                event_property_name: "sent",
                "{}_sent_date".format(event_property_name): str(date.today()),
                "bets_{}_error".format(self.event_id): "",
            }
        )

    def handle_failure(self, response, case, repeat_record):
        update_case(
            case.domain,
            case.case_id,
            {
                self.get_event_property_name(case): (
                    "error"
                    if case.dynamic_case_properties().get(self.get_event_property_name(case)) != 'sent'
                    else 'sent'
                ),
                "bets_{}_error".format(self.event_id): unicode(response.json()),
            }
        )


class BETSSuccessfulTreatmentPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = SUCCESSFUL_TREATMENT_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_successful_treatment_payload(episode_case).payload_json())


class BETSDiagnosisAndNotificationPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = DIAGNOSIS_AND_NOTIFICATION_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_diagnosis_and_notification_payload(episode_case).payload_json())


class BETSAYUSHReferralPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = AYUSH_REFERRAL_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_ayush_referral_payload(episode_case).payload_json())


class BETSUserPayloadGenerator(UserPayloadGenerator):
    # Not all of these are used, but the endpoint will fail without them
    user_data_fields = [
        "secondary_pincode", "address_line_1", "use_new_ids",
        "pcc_pharmacy_affiliation", "plc_lab_collection_center_name",
        "commcare_project", "pcp_professional_org_membership", "pincode",
        "id_issuer_body", "agency_status", "secondary_date_of_birth",
        "tb_corner", "pcc_pharmacy_name", "id_device_number",
        "secondary_gender", "plc_tb_tests", "landline_no", "id_issuer_number",
        "secondary_landline_no", "plc_lab_or_collection_center",
        "secondary_first_name", "commcare_primary_case_sharing_id",
        "pcp_qualification", "pac_qualification", "secondary_unique_id_type",
        "email", "commcare_location_id", "issuing_authority",
        "pcc_tb_drugs_in_stock", "secondary_mobile_no_2",
        "secondary_mobile_no_1", "secondary_middle_name", "plc_accredidation",
        "mobile_no_2", "commcare_location_ids", "mobile_no_1", "is_test",
        "secondary_email", "id_device_body", "secondary_unique_id_Number",
        "plc_hf_if_nikshay", "usertype", "user_level", "gender",
        "secondary_address_line_1", "secondary_last_name",
        "secondary_address_line_2", "address_line_2", "registration_number",
        "nikshay_id",
    ]

    def get_payload(self, repeat_record, user):
        user_json = self.serialize(repeat_record.domain, user)
        return json.dumps(user_json, cls=DjangoJSONEncoder)

    @staticmethod
    def serialize(domain, user):
        location = user.get_sql_location(domain)
        user_json = {
            "username": user.raw_username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "default_phone_number": user.default_phone_number,
            "id": user._id,
            "phone_numbers": user.phone_numbers,
            "email": user.email,
            "dtoLocation": _get_district_location(location),
            "privateSectorOrgId": location.metadata.get('private_sector_org_id', ''),
            "resource_uri": "",
        }
        user_json['user_data'] = {
            field: user.user_data.get(field, "")
            for field in BETSUserPayloadGenerator.user_data_fields
        }
        return user_json


class BETSLocationPayloadGenerator(LocationPayloadGenerator):

    def get_payload(self, repeat_record, location):
        return json.dumps(get_bets_location_json(location))


class BETSBeneficiaryPayloadGenerator(BasePayloadGenerator):
    case_properties = [
        "age", "age_entered", "case_name", "case_type", "current_address",
        "current_address_block_taluka_mandal",
        "current_address_district_choice", "current_address_first_line",
        "current_address_postal_code", "current_address_state_choice",
        "current_address_village_town_city", "current_address_ward",
        "current_episode_type", "dataset", "date_opened", "dob", "dob_known",
        "enrolled_in_private", "external_id", "facility_assigned_to",
        "first_name", "husband_father_name", "id_original_beneficiary_count",
        "id_original_device_number", "id_original_issuer_number",
        "language_preference", "last_name", "other_id_type", "person_id",
        "phi", "phone_number", "send_alerts", "sex", "tu_choice",
    ]

    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, person_case):
        case_json = {
            "case_id": person_case.case_id,
            "closed": person_case.closed,
            "date_closed": person_case.closed_on,
            "date_modified": person_case.modified_on,
            "domain": person_case.domain,
            "id": person_case.case_id,
            "indices": {},
            "resource_uri": "",
            "server_date_modified": person_case.server_modified_on,
            "server_date_opened": person_case.opened_on,
            "user_id": person_case.modified_by,
            "xform_ids": [],
        }
        case_properties = person_case.dynamic_case_properties()
        case_json["properties"] = {
            prop: case_properties.get(prop, "")
            for prop in self.case_properties
        }
        case_json["properties"]["owner_id"] = person_case.owner_id
        return json.dumps(case_json, cls=DjangoJSONEncoder)
