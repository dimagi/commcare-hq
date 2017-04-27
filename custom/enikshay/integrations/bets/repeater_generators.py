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
from custom.enikshay.const import DATE_FULLFILLED, VOUCHER_ID, FULLFILLED_BY_ID, AMOUNT_APPROVED, \
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


class IncentivePayload(BETSPayload):
    EpisodeID = jsonobject.StringProperty(required=False)


class VoucherPayload(BETSPayload):

    VoucherID = jsonobject.StringProperty(required=False)
    Amount = jsonobject.DecimalProperty(required=False)


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


