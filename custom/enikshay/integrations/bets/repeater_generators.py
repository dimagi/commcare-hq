import json

import jsonobject
from datetime import datetime, date

import pytz
from pytz import timezone

from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.exceptions import RequestConnectionError
from corehq.apps.repeaters.repeater_generators import BasePayloadGenerator, LocationPayloadGenerator
from custom.enikshay.case_utils import update_case, get_person_case_from_episode
from custom.enikshay.const import (
    DATE_FULFILLED,
    VOUCHER_ID,
    FULFILLED_BY_ID,
    FULFILLED_BY_LOCATION_ID,
    AMOUNT_APPROVED,
    TREATMENT_OUTCOME_DATE,
    PRESCRIPTION_TOTAL_DAYS_THRESHOLD,
    LAST_VOUCHER_CREATED_BY_ID,
    NOTIFYING_PROVIDER_USER_ID,
    INVESTIGATION_TYPE,
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
            msg = "Location with id {location_id} not found.".format(location_id)
            if field_name and related_case_type and related_case_id:
                msg += " This is the {field_name} for {related_case_type} with id: {related_case_id}".format(
                    field_name=field_name,
                    related_case_type=related_case_type,
                    related_case_id=related_case_id,
                )
            raise NikshayLocationNotFound(msg)

    @classmethod
    def _get_district_location(cls, pcp_location):
        try:
            district_location = pcp_location.parent
            if district_location.location_type.code != 'dto':
                raise NikshayLocationNotFound("Parent location of {} is not a district".format(pcp_location))
            return pcp_location.parent.location_id
        except AttributeError:
            raise NikshayLocationNotFound("Parent location of {} not found".format(pcp_location))


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

        return cls(
            EventID=TREATMENT_180_EVENT,
            EventOccurDate=episode_case_properties.get(TREATMENT_OUTCOME_DATE),
            BeneficiaryUUID=episode_case_properties.get(LAST_VOUCHER_CREATED_BY_ID),
            BeneficiaryType="patient",
            EpisodeID=episode_case.case_id,
            Location=person_case.owner_id,
            DTOLocation=cls._get_district_location(pcp_location),
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
            DTOLocation=cls._get_district_location(pcp_location)
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
            DTOLocation=cls._get_district_location(location),
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
            DTOLocation=cls._get_district_location(location),
        )

    @classmethod
    def create_ayush_referral_payload(cls, episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()

        location = cls._get_location(
            episode_case_properties.get("created_by_user_location_id"),
            field_name="created_by_user_location_id",
            related_case_type="episode",
            related_case_id=episode_case.case_id,
        )

        return cls(
            EventID=AYUSH_REFERRAL_EVENT,
            EventOccurDate=cls._india_now(),
            BeneficiaryUUID=episode_case_properties.get("created_by_user_id"),
            BeneficiaryType='ayush_other',
            EpisodeID=episode_case.case_id,
            Location=episode_case_properties.get("created_by_user_location_id"),
            DTOLocation=cls._get_district_location(location),
        )


class VoucherPayload(BETSPayload):

    VoucherID = jsonobject.StringProperty(required=False)
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

        return cls(
            EventID=event_id,
            EventOccurDate=voucher_case_properties.get(DATE_FULFILLED),
            VoucherID=voucher_case_properties.get(VOUCHER_ID),
            BeneficiaryUUID=fulfilled_by_id,
            BeneficiaryType=LOCATION_TYPE_MAP[location.location_type.code],
            Location=fulfilled_by_location_id,
            Amount=voucher_case_properties.get(AMOUNT_APPROVED),
            DTOLocation=cls._get_district_location(location),
            InvestigationType=voucher_case_properties.get(INVESTIGATION_TYPE),
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
        ).to_json())


class BETS180TreatmentPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = TREATMENT_180_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_180_treatment_payload(episode_case).to_json())


class BETSDrugRefillPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = DRUG_REFILL_EVENT

    @staticmethod
    def _get_prescription_threshold_to_send(episode_case_properties):
        from custom.enikshay.integrations.bets.repeaters import BETSDrugRefillRepeater
        thresholds_to_send = [
            n for n in TOTAL_DAY_THRESHOLDS
            if BETSDrugRefillRepeater.prescription_total_days_threshold_in_trigger_state(
                episode_case_properties, n
            )
        ]
        assert len(thresholds_to_send) == 1, \
            "Repeater should not have allowed to forward if there were more or less than one threshold to trigger"

        return thresholds_to_send[0]

    def get_payload(self, repeat_record, episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()
        n = self._get_prescription_threshold_to_send(episode_case_properties)
        return json.dumps(IncentivePayload.create_drug_refill_payload(episode_case, n).to_json())

    def get_event_property_name(self, episode_case):
        n = self._get_prescription_threshold_to_send(episode_case.dynamic_case_properties())
        return "event_{}_{}".format(self.event_id, n)

    def handle_success(self, response, case, repeat_record):
        if response.status_code == 201:
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
        if 400 <= response.status_code <= 500:
            update_case(
                case.domain,
                case.case_id,
                {
                    self.get_event_property_name(case): (
                        "error"
                        if case.dynamic_case_properties().get(self.get_event_property_name(case)) != 'sent'
                        else 'sent'
                    ),
                    "bets_{}_error".format(self.event_id): "{}: {}".format(
                        response.status_code,
                        response.json().get('error')
                    ),
                }
            )


class BETSSuccessfulTreatmentPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = SUCCESSFUL_TREATMENT_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_successful_treatment_payload(episode_case).to_json())


class BETSDiagnosisAndNotificationPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = DIAGNOSIS_AND_NOTIFICATION_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_diagnosis_and_notification_payload(episode_case).to_json())


class BETSAYUSHReferralPayloadGenerator(IncentivePayloadGenerator):
    deprecated_format_names = ('case_json',)
    event_id = AYUSH_REFERRAL_EVENT

    def get_payload(self, repeat_record, episode_case):
        return json.dumps(IncentivePayload.create_ayush_referral_payload(episode_case).to_json())


class BETSLocationPayloadGenerator(LocationPayloadGenerator):

    def get_payload(self, repeat_record, location):
        payload = location.to_json()
        # Override lineage to use a custom format for BETS
        payload['ancestors_by_type'] = {
            ancestor.location_type.name: ancestor.location_id
            for ancestor in location.get_ancestors()
        }
        return payload
