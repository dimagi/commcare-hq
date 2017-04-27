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
from custom.enikshay.const import DATE_FULFILLED, VOUCHER_ID, FULFILLED_BY_ID, AMOUNT_APPROVED, \
    TREATMENT_180_EVENT, TREATMENT_OUTCOME_DATE, VOUCHER_EVENT_ID, DRUG_REFILL_EVENT, SUCCESSFUL_TREATMENT_EVENT, \
    DIAGNOSIS_AND_NOTIFICATION_EVENT, AYUSH_REFERRAL_EVENT, LOCATION_TYPE_MAP
from custom.enikshay.exceptions import NikshayLocationNotFound
from custom.enikshay.integrations.bets.repeaters import BETSVoucherRepeater, BETS180TreatmentRepeater, \
    BETSDrugRefillRepeater, BETSSuccessfulTreatmentRepeater, BETSDiagnosisAndNotificationRepeater, \
    BETSAYUSHReferralRepeater


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


class VoucherPayload(BETSPayload):

    VoucherID = jsonobject.StringProperty(required=False)
    Amount = jsonobject.DecimalProperty(required=False)

    @classmethod
    def create_voucher_payload(cls, voucher_case):
        voucher_case_properties = voucher_case.dynamic_case_properties()
        fulfilled_by_id = voucher_case_properties.get(FULFILLED_BY_ID)

        location = cls._get_location(
            fulfilled_by_id,
            field_name=FULFILLED_BY_ID,
            related_case_type="voucher",
            related_case_id=voucher_case.case_id
        )

        return cls(
            EventID=VOUCHER_EVENT_ID,
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


@RegisterGenerator(BETSVoucherRepeater, 'case_json', 'JSON', is_default=True)
class BETSVoucherPayloadGenerator(BETSBasePayloadGenerator):
    event_id = VOUCHER_EVENT_ID

    def get_payload(self, repeat_record, voucher_case):
        return json.dumps(VoucherPayload.create_voucher_payload(voucher_case).to_json())

