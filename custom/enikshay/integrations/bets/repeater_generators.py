import json

import jsonobject
from datetime import datetime

import pytz
from pytz import timezone

from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.exceptions import RequestConnectionError
from corehq.apps.repeaters.repeater_generators import RegisterGenerator, BasePayloadGenerator
from custom.enikshay.case_utils import update_case, get_person_case_from_episode, get_open_episode_case_from_person, \
    get_person_case_from_voucher
from custom.enikshay.const import (
    DATE_FULFILLED,
    VOUCHER_ID,
    FULFILLED_BY_ID,
    AMOUNT_APPROVED,
    TREATMENT_OUTCOME_DATE,
)
from custom.enikshay.integrations.bets.const import (
    TREATMENT_180_EVENT,
    DRUG_REFILL_EVENT,
    SUCCESSFUL_TREATMENT_EVENT,
    DIAGNOSIS_AND_NOTIFICATION_EVENT,
    AYUSH_REFERRAL_EVENT,
    LOCATION_TYPE_MAP,
    CHEMIST_VOUCHER_EVENT, LAB_VOUCHER_EVENT)
from custom.enikshay.exceptions import NikshayLocationNotFound
from custom.enikshay.integrations.bets.repeaters import BETS180TreatmentRepeater, \
    BETSDrugRefillRepeater, BETSSuccessfulTreatmentRepeater, BETSDiagnosisAndNotificationRepeater, \
    BETSAYUSHReferralRepeater, ChemistBETSVoucherRepeater, LabBETSVoucherRepeater


class BETSPayload(jsonobject.JsonObject):

    EventID = jsonobject.StringProperty(required=True)
    EventOccurDate = jsonobject.StringProperty(required=True)
    BeneficiaryUUID = jsonobject.StringProperty(required=True)
    BeneficiaryType = jsonobject.StringProperty(required=True)
    Location = jsonobject.StringProperty(required=True)

    @classmethod
    def _get_location(cls, location_id, field_name=None, related_case_type=None, related_case_id=None):
        try:
            return SQLLocation.objects.get(location_id=location_id)
        except SQLLocation.DoesNotExist:
            msg = "Location with id {location_id} not found.".format(location_id)
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
        location = cls._get_location(
            person_case.owner_id,
            field_name="owner_id",
            related_case_type="person",
            related_case_id=person_case.case_id
        )

        return cls(
            EventID=TREATMENT_180_EVENT,
            EventOccurDate=episode_case_properties.get(TREATMENT_OUTCOME_DATE),
            BeneficiaryUUID=person_case.owner_id,
            BeneficiaryType="patient",
            EpisodeID=episode_case.case_id,
            Location=location.metadata["nikshay_code"],
        )

    @classmethod
    def create_drug_refill_payload(cls, voucher_case):
        voucher_case_properties = voucher_case.dynamic_case_properties()
        person_case = get_person_case_from_voucher(voucher_case.domain, voucher_case.case_id)
        episode_case = get_open_episode_case_from_person(person_case.domain, person_case.case_id)

        location = cls._get_location(
            person_case.owner_id,
            field_name="owner_id",
            related_case_type="person",
            related_case_id=person_case.case_id,
        )

        return cls(
            EventID=DRUG_REFILL_EVENT,
            EventOccurDate=voucher_case_properties.get("date_approved"),
            BeneficiaryUUID=person_case.case_id,
            BeneficiaryType="patient",
            EpisodeID=episode_case.case_id,
            Location=location.metadata["nikshay_code"],
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
            EventOccurDate=episode_case_properties[TREATMENT_OUTCOME_DATE],
            BeneficiaryUUID=person_case.case_id,
            BeneficiaryType="patient",
            EpisodeID=episode_case.case_id,
            Location=location.metadata["nikshay_code"],
        )

    @staticmethod
    def _india_now():
        utc_now = pytz.UTC.localize(datetime.utcnow())
        india_now = timezone('Asia/Kolkata').localize(utc_now)
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
            BeneficiaryUUID=person_case.owner_id,
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type],
            EpisodeID=episode_case.case_id,
            Location=location.metadata["nikshay_code"],
        )

    @classmethod
    def create_ayush_referral_payload(cls, episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()
        person_case = get_person_case_from_episode(episode_case.domain, episode_case.case_id)

        location = cls._get_location(
            episode_case_properties.get("presumptive_referral_by_ayush"),
            field_name="presumptive_referral_by_ayush",
            related_case_type="episode",
            related_case_id=episode_case.case_id,
        )

        person_owner_location = cls._get_location(
            person_case.owner_id,
            field_name="owner_id",
            related_case_type="person",
            related_case_id=person_case.case_id
        )

        return cls(
            EventID=AYUSH_REFERRAL_EVENT,
            EventOccurDate=cls._india_now(),
            BeneficiaryUUID=episode_case_properties.get("presumptive_referral_by_ayush"),
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type],
            EpisodeID=episode_case.case_id,
            Location=person_owner_location.metadata["nikshay_code"],
        )


class VoucherPayload(BETSPayload):

    VoucherID = jsonobject.StringProperty(required=False)
    Amount = jsonobject.DecimalProperty(required=False)

    @classmethod
    def create_voucher_payload(cls, voucher_case):
        voucher_case_properties = voucher_case.dynamic_case_properties()
        fulfilled_by_id = voucher_case_properties.get(FULFILLED_BY_ID)
        event_id = {
            "prescription": CHEMIST_VOUCHER_EVENT,
            "test": LAB_VOUCHER_EVENT,
        }[voucher_case_properties['voucher_type']]

        location = cls._get_location(
            fulfilled_by_id,
            field_name=FULFILLED_BY_ID,
            related_case_type="voucher",
            related_case_id=voucher_case.case_id
        )

        return cls(
            EventID=event_id,
            EventOccurDate=voucher_case_properties.get(DATE_FULFILLED),
            VoucherID=voucher_case_properties.get(VOUCHER_ID),
            BeneficiaryUUID=fulfilled_by_id,
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type],
            Location=location.metadata["nikshay_code"],
            Amount=voucher_case_properties.get(AMOUNT_APPROVED),
        )


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
        if response.status_code == 201:
            update_case(
                case.domain,
                case.case_id,
                {
                    self.event_property_name: "sent",
                    "bets_{}_error".format(self.event_id): ""
                }
            )

    def handle_failure(self, response, case, repeat_record):
        if 400 <= response.status_code <= 500:
            update_case(
                case.domain,
                case.case_id,
                {
                    self.event_property_name: (
                        "error"
                        if case.dynamic_case_properties().get(self.event_property_name) != 'sent'
                        else 'sent'
                    ),
                    "bets_{}_error".format(self.event_id): "{}: {}".format(
                        response.status_code,
                        response.json().get('error')
                    ),
                }
            )


class BaseBETSVoucherPayloadGenerator(BETSBasePayloadGenerator):

    def get_test_payload(self, domain):
        return json.dumps(VoucherPayload(
            VoucherID="DUMMY-VOUCHER-ID",
            Amount=0,
            EventID="DUMMY-EVENT-ID",
            EventOccurDate="2017-01-01",
            BeneficiaryUUID="DUMMY-BENEFICIARY-ID",
            BeneficiaryType="chemist",
            location="DUMMY-LOCATION",
        ).to_json())

    def get_payload(self, repeat_record, voucher_case):
        return json.dumps(VoucherPayload.create_voucher_payload(voucher_case).to_json())


@RegisterGenerator(ChemistBETSVoucherRepeater, 'case_json', 'JSON', is_default=True)
class ChemistBETSVoucherPayloadGenerator(BaseBETSVoucherPayloadGenerator):
    event_id = CHEMIST_VOUCHER_EVENT


@RegisterGenerator(LabBETSVoucherRepeater, 'case_json', 'JSON', is_default=True)
class LabBETSVoucherPayloadGenerator(BaseBETSVoucherPayloadGenerator):
    event_id = LAB_VOUCHER_EVENT


class IncentivePayloadGenerator(BETSBasePayloadGenerator):

    def get_test_payload(self, domain):
        return json.dumps(IncentivePayload(
            EpisodeID="DUMMY-EPISODE-ID",
            EventID="DUMMY-EVENT-ID",
            EventOccurDate="2017-01-01",
            BeneficiaryUUID="DUMMY-BENEFICIARY-ID",
            BeneficiaryType="chemist",
            location="DUMMY-LOCATION",
        ).to_json())


@RegisterGenerator(BETS180TreatmentRepeater, "case_json", "JSON", is_default=True)
class BETS180TreatmentPayloadGenerator(IncentivePayloadGenerator):
    event_id = TREATMENT_180_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_180_treatment_payload(episode_case).to_json())


@RegisterGenerator(BETSDrugRefillRepeater, "case_json", "JSON", is_default=True)
class BETSDrugRefillPayloadGenerator(IncentivePayloadGenerator):
    event_id = DRUG_REFILL_EVENT

    def get_payload(self, repeat_record, voucher_case):
        return json.dumps(IncentivePayload.create_drug_refill_payload(voucher_case).to_json())


@RegisterGenerator(BETSSuccessfulTreatmentRepeater, "case_json", "JSON", is_default=True)
class BETSSuccessfulTreatmentPayloadGenerator(IncentivePayloadGenerator):
    event_id = SUCCESSFUL_TREATMENT_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_successful_treatment_payload(episode_case).to_json())


@RegisterGenerator(BETSDiagnosisAndNotificationRepeater, "case_json", "JSON", is_default=True)
class BETSDiagnosisAndNotificationPayloadGenerator(IncentivePayloadGenerator):
    event_id = DIAGNOSIS_AND_NOTIFICATION_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_diagnosis_and_notification_payload(episode_case).to_json())


@RegisterGenerator(BETSAYUSHReferralRepeater, "case_json", "JSON", is_default=True)
class BETSAYUSHReferralPayloadGenerator(IncentivePayloadGenerator):
    event_id = AYUSH_REFERRAL_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_ayush_referral_payload(episode_case).to_json())
