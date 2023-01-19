import json
import uuid
from base64 import urlsafe_b64encode

from django.db import transaction
from django.http import QueryDict
from django.utils.translation import gettext as _

import attr

from casexml.apps.phone.xml import get_registration_element_data

from corehq.apps.auditcare.models import get_standard_headers
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.users.models import CouchUser
from corehq.motech.const import FIFTY_MB
from corehq.motech.generic_inbound.exceptions import GenericInboundUserError
from corehq.util import as_text
from corehq.util.view_utils import get_form_or_404


def make_url_key():
    raw_key = urlsafe_b64encode(uuid.uuid4().bytes).decode()
    return raw_key.removesuffix("==")


@attr.s(kw_only=True, frozen=True, auto_attribs=True)
class ApiRequest:
    domain: str
    couch_user: CouchUser
    request_method: str
    user_agent: str
    data: dict
    query: dict  # querystring key val pairs, vals are lists
    headers: dict

    @classmethod
    def from_request(cls, request):
        try:
            body = as_text(request.body)
        except UnicodeDecodeError:
            raise GenericInboundUserError(_("Unable to decode request body"))

        if len(body) > FIFTY_MB:
            raise GenericInboundUserError(_("Request exceeds 50MB size limit"))

        try:
            request_json = json.loads(body)
        except json.JSONDecodeError:
            raise GenericInboundUserError(_("Payload must be valid JSON"))
        return cls(
            domain=request.domain,
            couch_user=request.couch_user,
            request_method=request.method,
            user_agent=request.META.get('HTTP_USER_AGENT'),
            data=request_json,
            query=dict(request.GET.lists()),
            headers=get_standard_headers(request.META)
        )

    @classmethod
    def from_log(cls, log):
        try:
            request_json = json.loads(log.request_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GenericInboundUserError(_("Payload must be valid JSON"))
        return cls(
            domain=log.domain,
            couch_user=CouchUser.get_by_username(log.username),
            request_method=log.request_method,
            user_agent=log.request_headers.get('HTTP_USER_AGENT'),
            data=request_json,
            query=dict(QueryDict(log.request_query).lists()),
            headers=dict(log.request_headers),
        )

    def to_context(self):
        restore_user = self.couch_user.to_ota_restore_user(
            self.domain, request_user=self.couch_user)
        return get_evaluation_context(
            restore_user,
            self.request_method,
            self.query,
            self.headers,
            self.data,
        )


@attr.s(kw_only=True, frozen=True, auto_attribs=True)
class ApiResponse:
    status: int
    data: dict = None


def make_processing_attempt(response, request_log, is_retry=False):
    from corehq.motech.generic_inbound.models import ProcessingAttempt

    response_data = response.data or {}
    case_ids = [c['case_id'] for c in response_data.get('cases', [])]
    ProcessingAttempt.objects.create(
        is_retry=is_retry,
        log=request_log,
        response_status=response.status,
        raw_response=response_data,
        xform_id=response_data.get('form_id'),
        case_ids=case_ids,
    )


def get_evaluation_context(restore_user, method, query, headers, body):
    return EvaluationContext({
        'request': {
            'method': method,
            'query': query,
            'headers': headers
        },
        'body': body,
        'user': get_registration_element_data(restore_user)
    })


def reprocess_api_request(request_log):
    from corehq.motech.generic_inbound.models import RequestLog
    from corehq.motech.generic_inbound.core import execute_generic_api

    try:
        request_data = ApiRequest.from_log(request_log)
    except GenericInboundUserError as e:
        response = ApiResponse(status=400, data={'error': str(e)})
    else:
        response = execute_generic_api(request_log.api, request_data)

    with transaction.atomic():
        request_log.status = RequestLog.Status.from_status_code(response.status)
        request_log.attempts += 1
        request_log.response_status = response.status
        request_log.save()
        make_processing_attempt(response, request_log, is_retry=True)


def archive_api_request(request_log, user_id):
    attempts = request_log.processingattempt_set.filter(xform_id__isnull=False)
    for attempt in attempts:
        form = get_form_or_404(request_log.domain, attempt.xform_id)
        form.archive(user_id=user_id)
    _revert_api_request_log(request_log)


def _revert_api_request_log(request_log):
    from corehq.motech.generic_inbound.models import RequestLog
    if request_log.status == RequestLog.Status.SUCCESS:
        request_log.status = RequestLog.Status.REVERTED
        request_log.save()


def revert_api_request_from_form(form_id):
    from corehq.motech.generic_inbound.models import ProcessingAttempt
    try:
        attempt = ProcessingAttempt.objects.get(xform_id=form_id)
        _revert_api_request_log(attempt.log)
    except ProcessingAttempt.DoesNotExist:
        return
