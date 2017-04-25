"""
# https://docs.google.com/document/d/1RPPc7t9NhRjOOiedlRmtCt3wQSjAnWaj69v2g7QRzS0/edit
"""
import datetime
import json
from django.views.decorators.http import require_POST
from dimagi.utils.web import json_response
from dimagi.ext import jsonobject
from jsonobject.exceptions import BadValueError, WrappingAttributeError
# import JsonObject, StringProperty, ListProperty, DictProperty
# from dimagi.utils.decorators.memoized import memoized
from corehq.apps.domain.decorators import login_or_digest_or_basic_or_apikey

# TODO does this auth check domain?


from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from casexml.apps.case.const import CASE_INDEX_EXTENSION, UNOWNED_EXTENSION_OWNER_ID
from corehq.form_processor.exceptions import CaseNotFound
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.hqcase.utils import update_case


class ApiError(Exception):
    def __init__(self, msg, status_code):
        self.status_code = status_code
        super(ApiError, self).__init__(msg)


class VoucherUpdate(jsonobject.JsonObject):
    voucher_id = jsonobject.StringProperty(required=True)
    payment_status = jsonobject.StringProperty(required=True, choices=['success', 'failure'])
    payment_amount = jsonobject.IntegerProperty(required=False)
    failure_description = jsonobject.StringProperty(required=False)

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


def get_case(domain, case_id):
    case_accessor = CaseAccessors(domain)
    return case_accessor.get_case(case_id)


@require_POST
@login_or_digest_or_basic_or_apikey()
def update_voucher(request, domain):
    try:
        request_json = json.loads(request.body)
    except ValueError:
        return json_response({"error": "Malformed JSON"}, status_code=400)
    try:
        update = VoucherUpdate.wrap(request_json)
    except BadValueError as e:
        return json_response({"error": e.message}, status_code=400)

    try:
        case = get_case(domain, update.voucher_id)
        if case.type != 'voucher':
            raise CaseNotFound()
    except CaseNotFound:
        return json_response({"error": "No case found with that ID"}, status_code=404)

    update_case(domain, update.voucher_id, case_properties=update.properties)

    return json_response({'status': "woo!"})
