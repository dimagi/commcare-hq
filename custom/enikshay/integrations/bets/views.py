"""
https://docs.google.com/document/d/1RPPc7t9NhRjOOiedlRmtCt3wQSjAnWaj69v2g7QRzS0/edit
"""
import datetime
import json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from dimagi.ext import jsonobject
from jsonobject.exceptions import BadValueError

from corehq import toggles
from corehq.apps.domain.decorators import login_or_digest_or_basic_or_apikey
from corehq.apps.hqcase.utils import update_case
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.case_utils import CASE_TYPE_VOUCHER, CASE_TYPE_EPISODE
from .const import BETS_EVENT_IDS


class ApiError(Exception):
    def __init__(self, msg, status_code):
        self.status_code = status_code
        super(ApiError, self).__init__(msg)


class VoucherUpdate(jsonobject.JsonObject):
    voucher_id = jsonobject.StringProperty(required=True)
    payment_status = jsonobject.StringProperty(required=True, choices=['success', 'failure'])
    payment_amount = jsonobject.DecimalProperty(required=False)
    failure_description = jsonobject.StringProperty(required=False)

    case_type = CASE_TYPE_VOUCHER

    @property
    def case_id(self):
        return self.voucher_id

    @property
    def properties(self):
        if self.payment_status == 'success':
            return {
                'state': 'paid',
                'amount_fulfilled': self.payment_amount,
                'date_fulfilled': datetime.datetime.utcnow().date().isoformat(),
            }
        else:
            return {
                'state': 'rejected',
                'reason_rejected': self.failure_description,
                'date_rejected': datetime.datetime.utcnow().date().isoformat(),
            }


class IncentiveUpdate(jsonobject.JsonObject):
    beneficiary_id = jsonobject.StringProperty(required=True)
    episode_id = jsonobject.StringProperty(required=True)
    payment_status = jsonobject.StringProperty(required=True, choices=['success', 'failure'])
    payment_amount = jsonobject.DecimalProperty(required=False)
    failure_description = jsonobject.StringProperty(required=False)
    bets_parent_event_id = jsonobject.StringProperty(
        required=False, choices=BETS_EVENT_IDS.values())

    case_type = CASE_TYPE_EPISODE

    @property
    def case_id(self):
        return self.episode_id

    @property
    def properties(self):
        status_key = 'tb_incentive_{}_status'.format(self.bets_parent_event_id)
        if self.payment_status == 'success':
            amount_key = 'tb_incentive_{}_amount'.format(self.bets_parent_event_id)
            date_key = 'tb_incentive_{}_payment_date'.format(self.bets_parent_event_id)
            return {
                status_key: 'paid',
                amount_key: self.payment_amount,
                date_key: datetime.datetime.utcnow().date().isoformat(),
            }
        else:
            date_key = 'tb_incentive_{}_rejection_date'.format(self.bets_parent_event_id)
            reason_key = 'tb_incentive_{}_rejection_reason'.format(self.bets_parent_event_id)
            return {
                status_key: 'rejected',
                date_key: datetime.datetime.utcnow().date().isoformat(),
                reason_key: self.failure_description,
            }


def get_case(domain, case_id):
    case_accessor = CaseAccessors(domain)
    return case_accessor.get_case(case_id)


def _get_case_update(request, domain, update_model):
    try:
        request_json = json.loads(request.body)
    except ValueError:
        raise ApiError(msg="Malformed JSON", status_code=400)
    try:
        update = update_model.wrap(request_json)
    except BadValueError as e:
        raise ApiError(msg=e.message, status_code=400)
    try:
        case = get_case(domain, update.case_id)
        if case.type != update.case_type:
            raise CaseNotFound()
    except CaseNotFound:
        raise ApiError(
            msg="No {} case found with that ID".format(update.case_type),
            status_code=404
        )
    return update


def _update_case_from_request(request, domain, update_model):
    try:
        update = _get_case_update(request, domain, update_model)
    except ApiError as e:
        if not settings.UNIT_TESTING:
            notify_exception(request, "BETS sent the eNikshay API a bad request.")
        return json_response({"error": e.message}, status_code=e.status_code)

    update_case(domain, update.case_id, case_properties=update.properties)

    return json_response({'status': "success"})


@require_POST
@csrf_exempt
@login_or_digest_or_basic_or_apikey()
@toggles.ENIKSHAY_API.required_decorator()
def update_voucher(request, domain):
    return _update_case_from_request(request, domain, VoucherUpdate)


@require_POST
@csrf_exempt
@login_or_digest_or_basic_or_apikey()
@toggles.ENIKSHAY_API.required_decorator()
def update_incentive(request, domain):
    return _update_case_from_request(request, domain, IncentiveUpdate)
