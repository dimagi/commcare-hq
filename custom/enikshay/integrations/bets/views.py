"""
https://docs.google.com/document/d/1RPPc7t9NhRjOOiedlRmtCt3wQSjAnWaj69v2g7QRzS0/edit
"""
from __future__ import absolute_import
import json

from dateutil import parser as date_parser
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from dimagi.ext import jsonobject
from jsonobject.exceptions import BadValueError

from corehq import toggles
from corehq.apps.domain.decorators import api_auth, two_factor_exempt
from corehq.apps.locations.resources.v0_5 import LocationResource
from corehq.motech.repeaters.views import AddCaseRepeaterView
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.case_utils import CASE_TYPE_VOUCHER, CASE_TYPE_EPISODE
from .const import BETS_EVENT_IDS
from .tasks import process_payment_confirmations
from .utils import get_bets_location_json

SUCCESS = "Success"
FAILURE = "Failure"


class ApiError(Exception):
    def __init__(self, msg, status_code):
        self.status_code = status_code
        super(ApiError, self).__init__(msg)


class FlexibleDateTimeProperty(jsonobject.DateTimeProperty):
    def _wrap(self, value):
        try:
            return date_parser.parse(value)
        except ValueError:
            return super(FlexibleDateTimeProperty, self)._wrap(value)


class PaymentUpdate(jsonobject.JsonObject):
    id = jsonobject.StringProperty(required=True)
    status = jsonobject.StringProperty(required=True, choices=[SUCCESS, FAILURE])
    amount = jsonobject.FloatProperty(required=False)
    paymentDate = FlexibleDateTimeProperty(required=True)
    comments = jsonobject.StringProperty(required=False)
    failureDescription = jsonobject.StringProperty(required=False)
    paymentMode = jsonobject.StringProperty(required=False)
    checkNumber = jsonobject.StringProperty(required=False)
    bankName = jsonobject.StringProperty(required=False)

    @classmethod
    def wrap(cls, data):
        amount = data.get('amount', None)
        if amount:
            try:
                float_amount = float(amount)
                data['amount'] = float_amount
            except (ValueError, TypeError):
                raise BadValueError("amount '{}' is not a number".format(amount))
        return super(PaymentUpdate, cls).wrap(data)

    @property
    def case_id(self):
        return self.id


class VoucherUpdate(PaymentUpdate):
    eventType = jsonobject.StringProperty(required=True, choices=['Voucher'])
    case_type = CASE_TYPE_VOUCHER

    @property
    def properties(self):
        if self.status == SUCCESS:
            return {
                'state': 'paid',
                'amount_paid': self.amount,
                'date_paid': self.paymentDate.date().isoformat(),
                'time_paid': self.paymentDate.time().isoformat(),
                'comments': self.comments or "",
                'payment_mode': self.paymentMode or "",
                'check_number': self.checkNumber or "",
                'bank_name': self.bankName or "",
            }
        else:
            return {
                'state': 'rejected',
                'comments': self.comments or "",
                'reason_rejected': self.failureDescription or "",
                'date_rejected': self.paymentDate.isoformat(),
            }


class IncentiveUpdate(PaymentUpdate):
    eventType = jsonobject.StringProperty(required=True, choices=['Incentive'])
    eventID = jsonobject.StringProperty(
        required=False, choices=BETS_EVENT_IDS)
    case_type = CASE_TYPE_EPISODE

    @property
    def properties(self):
        status_key = 'tb_incentive_{}_status'.format(self.eventID)
        comments_key = 'tb_incentive_{}_comments'.format(self.eventID)
        if self.status == SUCCESS:
            amount_key = 'tb_incentive_{}_amount'.format(self.eventID)
            date_key = 'tb_incentive_{}_payment_date'.format(self.eventID)
            payment_mode_key = 'tb_incentive_{}_payment_mode'.format(self.eventID)
            check_number_key = 'tb_incentive_{}_check_number'.format(self.eventID)
            bank_name_key = 'tb_incentive_{}_bank_name'.format(self.eventID)
            return {
                status_key: 'paid',
                amount_key: self.amount,
                date_key: self.paymentDate.isoformat(),
                comments_key: self.comments or "",
                payment_mode_key: self.paymentMode or "",
                check_number_key: self.checkNumber or "",
                bank_name_key: self.bankName or "",
            }
        else:
            date_key = 'tb_incentive_{}_rejection_date'.format(self.eventID)
            reason_key = 'tb_incentive_{}_rejection_reason'.format(self.eventID)
            return {
                status_key: 'rejected',
                date_key: self.paymentDate.isoformat(),
                reason_key: self.failureDescription or "",
                comments_key: self.comments or "",
            }


def get_case(domain, case_id):
    case_accessor = CaseAccessors(domain)
    return case_accessor.get_case(case_id)


def _get_case_updates(request, domain):
    try:
        request_json = json.loads(request.body)
    except ValueError:
        raise ApiError(msg="Malformed JSON", status_code=400)

    if not isinstance(request_json.get('response', None), list):
        raise ApiError(msg='Expected json of the form `{"response": []}`', status_code=400)

    updates = []
    for event_json in request_json['response']:
        if event_json.get('eventType', None) not in ('Voucher', 'Incentive'):
            msg = 'Expected "eventType": "Voucher" or "eventType": "Incentive"'
            raise ApiError(msg=msg, status_code=400)

        update_model = VoucherUpdate if event_json['eventType'] == 'Voucher' else IncentiveUpdate
        try:
            update = update_model.wrap(event_json)
        except BadValueError as e:
            raise ApiError(msg=e.message, status_code=400)
        updates.append(update)
    return updates


def _validate_updates_exist(domain, updates):
    """Validate that all cases in the payload exist and have the right type"""
    existing_case_types = {
        case.case_id: case.type for case in
        CaseAccessors(domain).get_cases([update.case_id for update in updates])
    }
    missing = [
        update for update in updates
        if existing_case_types.get(update.case_id, None) != update.case_type
    ]
    if missing:
        str_missing = '\n'.join(["{}: {}".format(update.case_type, update.case_id)
                                 for update in missing])
        raise ApiError(
            msg="The following cases were not found:\n{}".format(str_missing),
            status_code=404
        )
    return updates


@require_POST
@csrf_exempt
@api_auth
@two_factor_exempt
@toggles.ENIKSHAY_API.required_decorator()
def payment_confirmation(request, domain):
    try:
        updates = _get_case_updates(request, domain)
        updates = _validate_updates_exist(domain, updates)
    except ApiError as e:
        if not settings.UNIT_TESTING:
            notify_exception(request, "BETS sent the eNikshay API a bad request.")
        return json_response({"error": e.message}, status_code=e.status_code)

    process_payment_confirmations.delay(domain, updates)
    return json_response({'status': SUCCESS})


class ChemistBETSVoucherRepeaterView(AddCaseRepeaterView):
    urlname = 'chemist_bets_voucher_repeater'
    page_title = "BETS Chemist Vouchers"
    page_name = "BETS Chemist Vouchers (voucher case type)"


class LabBETSVoucherRepeaterView(AddCaseRepeaterView):
    urlname = 'lab_bets_voucher_repeater'
    page_title = "BETS Lab Vouchers"
    page_name = "BETS Lab Vouchers (voucher case type)"


class BETS180TreatmentRepeaterView(AddCaseRepeaterView):
    urlname = "bets_180_treatment_repeater"
    page_title = "MBBS+ Providers: 6 months (180 days) of private OR govt. FDCs with treatment outcome reported"
    page_name = "MBBS+ Providers: 6 months (180 days) of private OR govt. " \
                "FDCs with treatment outcome reported (episode case type)"


class BETSDrugRefillRepeaterView(AddCaseRepeaterView):
    urlname = "bets_drug_refill_repeater"
    page_title = "Patients: Cash transfer on subsequent drug refill"
    page_name = "Patients: Cash transfer on subsequent drug refill (episode case_type)"


class BETSSuccessfulTreatmentRepeaterView(AddCaseRepeaterView):
    urlname = "bets_successful_treatment_repeater"
    page_title = "Patients: Cash transfer on successful treatment completion"
    page_name = "Patients: Cash transfer on successful treatment completion (episode case type)"


class BETSDiagnosisAndNotificationRepeaterView(AddCaseRepeaterView):
    urlname = "bets_diagnosis_and_notification_repeater"
    page_title = "MBBS+ Providers: To provider for diagnosis and notification of TB case"
    page_name = "MBBS+ Providers: To provider for diagnosis and notification of TB case (episode case type)"


class BETSAYUSHReferralRepeaterView(AddCaseRepeaterView):
    urlname = "bets_ayush_referral_repeater"
    page_title = "AYUSH/Other provider: Registering and referral of a presumptive TB case in UATBC/e-Nikshay"
    page_name = "AYUSH/Other provider: Registering and referral of a presumptive TB " \
                "case in UATBC/e-Nikshay (episode case type)"


# accessible at /a/enikshay/bets/v0.5/location/?format=json
class BETSLocationResource(LocationResource):
    def dehydrate(self, bundle):
        bundle.data = get_bets_location_json(bundle.obj)
        return bundle
