from __future__ import absolute_import
from datetime import datetime, date
import json
import jsonobject
import phonenumbers

from django.core.serializers.json import DjangoJSONEncoder
from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from corehq.util.soft_assert import soft_assert
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.motech.repeaters.exceptions import RequestConnectionError
from corehq.motech.repeaters.repeater_generators import (
    BasePayloadGenerator, LocationPayloadGenerator, UserPayloadGenerator)
from custom.enikshay.case_utils import (
    update_case, get_person_case_from_episode, get_person_case_from_voucher)
from custom.enikshay.const import (
    DATE_FULFILLED,
    FULFILLED_BY_ID,
    FULFILLED_BY_LOCATION_ID,
    AMOUNT_APPROVED,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
    PRESCRIPTION_TOTAL_DAYS_THRESHOLD,
    LAST_VOUCHER_CREATED_BY_ID,
    NOTIFYING_PROVIDER_USER_ID,
    INVESTIGATION_TYPE,
    USERTYPE_DISPLAYS,
    FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE,
    BETS_DATE_PRESCRIPTION_THRESHOLD_MET,
    VOUCHER_ID,
)
from custom.enikshay.exceptions import NikshayLocationNotFound
from custom.enikshay.integrations.utils import string_to_date_or_None
from .const import (
    TREATMENT_180_EVENT,
    DRUG_REFILL_EVENT,
    SUCCESSFUL_TREATMENT_EVENT,
    DIAGNOSIS_AND_NOTIFICATION_EVENT,
    AYUSH_REFERRAL_EVENT,
    LOCATION_TYPE_MAP,
    CHEMIST_VOUCHER_EVENT,
    LAB_VOUCHER_EVENT,
    TOTAL_DAY_THRESHOLDS
)
from .utils import get_bets_location_json
import six


def _get_district_location_id(pcp_location):
    return _get_district_location(pcp_location).location_id


def _get_district_location(pcp_location):
    try:
        district_location = pcp_location.parent
        if district_location.location_type.code != 'dto':
            raise NikshayLocationNotFound("Parent location of {} is not a district".format(pcp_location))
        return district_location
    except AttributeError:
        raise NikshayLocationNotFound("Parent location of {} not found".format(pcp_location))


class BETSPayload(jsonobject.JsonObject):

    EventID = jsonobject.StringProperty(required=True)
    EventOccurDate = jsonobject.DateProperty(required=True)
    BeneficiaryUUID = jsonobject.StringProperty(required=True)
    BeneficiaryType = jsonobject.StringProperty(required=True)
    Location = jsonobject.StringProperty(required=True)
    DTOLocation = jsonobject.StringProperty(required=True)
    PersonId = jsonobject.StringProperty(required=False)
    AgencyId = jsonobject.StringProperty(required=False)
    EnikshayApprover = jsonobject.StringProperty(required=False)
    EnikshayRole = jsonobject.StringProperty(required=False)
    EnikshayApprovalDate = jsonobject.StringProperty(required=False)

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

    @staticmethod
    def _get_agency_id(episode_case):
        agency_id = episode_case.get_case_property('bets_notifying_provider_user_id')
        if not agency_id:
            raise NikshayLocationNotFound(
                "Episode {} does not have an agency".format(episode_case.case_id))
        agency_user = CommCareUser.get_by_user_id(agency_id)
        return agency_user.raw_username

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

        treatment_outcome_date = string_to_date_or_None(
            episode_case_properties.get(TREATMENT_OUTCOME_DATE))
        if treatment_outcome_date is None:
            treatment_outcome_date = datetime.utcnow().date()

        return cls(
            EventID=TREATMENT_180_EVENT,
            EventOccurDate=treatment_outcome_date,
            BeneficiaryUUID=episode_case_properties.get(LAST_VOUCHER_CREATED_BY_ID),
            BeneficiaryType="mbbs",
            EpisodeID=episode_case.case_id,
            Location=person_case.owner_id,
            DTOLocation=_get_district_location_id(pcp_location),
            PersonId=person_case.get_case_property('person_id'),
            AgencyId=cls._get_agency_id(episode_case),  # not migrated from UATBC, so we're good
            # Incentives are not yet approved in eNikshay
            EnikshayApprover=None,
            EnikshayRole=None,
            EnikshayApprovalDate=None,
        )

    @classmethod
    def create_drug_refill_payload(cls, episode_case, n):
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)
        event_date = string_to_date_or_None(
            episode_case_properties.get(PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(n)))

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
            DTOLocation=_get_district_location_id(pcp_location),
            PersonId=person_case.get_case_property('person_id'),
            AgencyId=cls._get_agency_id(episode_case),  # we don't have this for migrated cases
            # Incentives are not yet approved in eNikshay
            EnikshayApprover=None,
            EnikshayRole=None,
            EnikshayApprovalDate=None,
        )

    @staticmethod
    def _get_successful_treatment_date(episode_case):
        completed_date = None
        if episode_case.get_case_property(TREATMENT_OUTCOME) in ("cured", "treatment_completed"):
            completed_date = episode_case.get_case_property(TREATMENT_OUTCOME_DATE)
            if not completed_date:
                # the treatment_outcome_date property used to be called
                # "rx_outcome_date", and was changed at some point. Older cases
                # still have the rx_outcome_date property set.
                completed_date = episode_case.get_case_property('rx_outcome_date')

        threshold_met_date = episode_case.get_case_property(BETS_DATE_PRESCRIPTION_THRESHOLD_MET)

        if completed_date is None and threshold_met_date is None:
            raise AssertionError("No treatment completion date found for episode {}. "
                                 "How was this triggered?".format(episode_case.case_id))

        # We don't know whether the trigger fired because the threshold was met
        # or because treatment ended.  Just use whichever happened first.
        return string_to_date_or_None(
            min([_f for _f in [completed_date, threshold_met_date] if _f]))

    @classmethod
    def create_successful_treatment_payload(cls, episode_case):
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)

        if person_case.owner_id == ARCHIVED_CASE_OWNER_ID:
            owner_id = person_case.dynamic_case_properties().get('last_owner')
            location = cls._get_location(
                person_case.dynamic_case_properties().get('last_owner'),
                field_name="last_owner",
                related_case_type="person",
                related_case_id=person_case.case_id,
            )
        else:
            owner_id = person_case.owner_id
            location = cls._get_location(
                person_case.owner_id,
                field_name="owner_id",
                related_case_type="person",
                related_case_id=person_case.case_id
            )

        return cls(
            EventID=SUCCESSFUL_TREATMENT_EVENT,
            EventOccurDate=cls._get_successful_treatment_date(episode_case),
            BeneficiaryUUID=person_case.case_id,
            BeneficiaryType="patient",
            EpisodeID=episode_case.case_id,
            Location=owner_id,
            DTOLocation=_get_district_location_id(location),
            PersonId=person_case.get_case_property('person_id'),
            AgencyId=cls._get_agency_id(episode_case),  # we don't have this for migrated cases
            # Incentives are not yet approved in eNikshay
            EnikshayApprover=None,
            EnikshayRole=None,
            EnikshayApprovalDate=None,
        )

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
            EventOccurDate=string_to_date_or_None(
                episode_case.get_case_property(FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE)),
            BeneficiaryUUID=episode_case.dynamic_case_properties().get(NOTIFYING_PROVIDER_USER_ID),
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type.code],
            EpisodeID=episode_case.case_id,
            Location=person_case.owner_id,
            DTOLocation=_get_district_location_id(location),
            PersonId=person_case.get_case_property('person_id'),
            AgencyId=cls._get_agency_id(episode_case),  # not migrated from UATBC, so we're good
            # Incentives are not yet approved in eNikshay
            EnikshayApprover=None,
            EnikshayRole=None,
            EnikshayApprovalDate=None,
        )

    @classmethod
    def create_ayush_referral_payload(cls, episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)

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
            EventOccurDate=string_to_date_or_None(
                episode_case.get_case_property(FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE)),
            BeneficiaryUUID=location.user_id,
            BeneficiaryType='ayush_other',
            EpisodeID=episode_case.case_id,
            Location=episode_case_properties.get("registered_by"),
            DTOLocation=_get_district_location_id(location),
            PersonId=person_case.get_case_property('person_id'),
            AgencyId=cls._get_agency_id(episode_case),  # not migrated from UATBC, so we're good
            # Incentives are not yet approved in eNikshay
            EnikshayApprover=None,
            EnikshayRole=None,
            EnikshayApprovalDate=None,
        )

    def payload_json(self):
        return {"incentive_details": [self.to_json()]}


class VoucherPayload(BETSPayload):

    VoucherID = jsonobject.StringProperty(required=False)
    ReadableVoucherID = jsonobject.StringProperty(required=False)
    Amount = jsonobject.StringProperty(required=False)

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

        person_case = get_person_case_from_voucher(voucher_case.domain, voucher_case.case_id)
        agency_user = CommCareUser.get_by_user_id(
            voucher_case.get_case_property('voucher_fulfilled_by_id'))

        approver_id = voucher_case.get_case_property('voucher_approved_by_id')
        if not approver_id:
            raise AssertionError("Voucher does not have an approver")
        approver = CommCareUser.get_by_user_id(approver_id)
        approver_name = approver.name
        usertype = approver.user_data.get('usertype')
        approver_usertype = USERTYPE_DISPLAYS.get(usertype, usertype)

        return cls(
            EventID=event_id,
            EventOccurDate=string_to_date_or_None(
                voucher_case_properties.get(DATE_FULFILLED)),
            VoucherID=voucher_case.case_id,
            ReadableVoucherID=voucher_case.get_case_property(VOUCHER_ID),
            BeneficiaryUUID=fulfilled_by_id,
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type.code],
            Location=fulfilled_by_location_id,
            # always round to nearest whole number, but send a string...
            Amount=str(int(round(float(voucher_case_properties.get(AMOUNT_APPROVED))))),
            DTOLocation=_get_district_location_id(location),
            InvestigationType=voucher_case_properties.get(INVESTIGATION_TYPE),
            PersonId=person_case.get_case_property('person_id'),
            AgencyId=agency_user.raw_username,
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
                "bets_{}_error".format(self.event_id): u"RequestConnectionError: {}".format(six.text_type(exception))
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
                "bets_{}_error".format(self.event_id): six.text_type(response.json()),
            }
        )


class BaseBETSVoucherPayloadGenerator(BETSBasePayloadGenerator):

    def get_test_payload(self, domain):
        return json.dumps(VoucherPayload(
            VoucherID="DUMMY-VOUCHER-ID",
            Amount="0",
            EventID="DUMMY-EVENT-ID",
            EventOccurDate=datetime.date(2017, 1, 1),
            BeneficiaryUUID="DUMMY-BENEFICIARY-ID",
            BeneficiaryType="chemist",
            Location="DUMMY-LOCATION",
            DTOLocation="DUMMY-LOCATION",
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
            EventOccurDate=datetime.date(2017, 1, 1),
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
    def _get_prescription_threshold_to_send(episode_case, check_already_sent=True):
        from custom.enikshay.integrations.bets.repeaters import BETSDrugRefillRepeater
        thresholds_to_send = [
            n for n in TOTAL_DAY_THRESHOLDS
            if BETSDrugRefillRepeater.prescription_total_days_threshold_in_trigger_state(
                episode_case.dynamic_case_properties(), n, check_already_sent=check_already_sent
            )
        ]
        if check_already_sent:
            _assert = soft_assert('{}@{}.com'.format('frener', 'dimagi'))
            message = ("Repeater should not have allowed to forward if there were more or less than"
                       "one threshold to trigger. Episode case: {}".format(episode_case.case_id))
            _assert(len(thresholds_to_send) == 1, message)

        try:
            return thresholds_to_send[-1]
        except IndexError:
            return 0

    def get_payload(self, repeat_record, episode_case):
        n = self._get_prescription_threshold_to_send(episode_case, check_already_sent=False)
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
                "bets_{}_error".format(self.event_id): six.text_type(response.json()),
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
        from .utils import get_bets_user_json
        user_json = get_bets_user_json(repeat_record.domain, user)
        return json.dumps(user_json, cls=DjangoJSONEncoder)

    def handle_success(self, response, user, repeat_record):
        # re-fetch the user so we don't get a document update conflict
        user = CommCareUser.get(user._id)
        existing_ids = user.user_data.get('BETS_user_repeat_record_ids')
        if existing_ids:
            user.user_data['BETS_user_repeat_record_ids'] = "{} {}".format(
                existing_ids,
                repeat_record._id
            )                   # space separated list to follow xform convention
        else:
            user.user_data['BETS_user_repeat_record_ids'] = repeat_record._id
        user.save()


class BETSLocationPayloadGenerator(LocationPayloadGenerator):

    def get_payload(self, repeat_record, location):
        return json.dumps(get_bets_location_json(location))

    def handle_success(self, response, location, repeat_record):
        location.refresh_from_db()
        existing_ids = location.metadata.get('BETS_location_repeat_record_ids')
        if existing_ids:
            location.metadata['BETS_location_repeat_record_ids'] = "{} {}".format(
                existing_ids,
                repeat_record._id
            )                   # space separated list to follow xform convention
        else:
            location.metadata['BETS_location_repeat_record_ids'] = repeat_record._id
        location.save()


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
        "phi", "send_alerts", "sex", "tu_choice",
    ]

    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, person_case):
        case_json = self.serialize(person_case)
        return json.dumps(case_json, cls=DjangoJSONEncoder)

    @staticmethod
    def serialize(person_case):
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
            for prop in BETSBeneficiaryPayloadGenerator.case_properties
        }
        case_json["properties"]["owner_id"] = person_case.owner_id
        # This is the "real" phone number
        case_json["properties"]["phone_number"] = get_national_number(
            case_properties.get("contact_phone_number", "")
        )
        return case_json


def get_national_number(phonenumber):
    try:
        return str(phonenumbers.parse(phonenumber, "IN").national_number)
    except phonenumbers.NumberParseException:
        return ""
