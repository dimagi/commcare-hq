import json
import uuid
from base64 import urlsafe_b64encode
from functools import cached_property

from django.conf import settings
from django.db import transaction
from django.http import QueryDict, HttpResponse, JsonResponse
from django.utils.translation import gettext as _

import attr

from casexml.apps.phone.xml import get_registration_element_data

from corehq.apps.auditcare.models import get_standard_headers
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.users.models import CouchUser
from corehq.motech.generic_inbound.exceptions import GenericInboundUserError, GenericInboundApiError
from corehq.motech.generic_inbound.models import RequestLog
from corehq.util import as_text
from corehq.util.view_utils import get_form_or_404
from dimagi.utils.web import get_ip


# exclude these headers as the may expose internal / sensitive information
EXCLUDE_HEADERS = [
    'X_FORWARDED_HOST',
    'X_FORWARDED_SERVER',
    'VIA',
    'HTTP_CONNECTION',
    'HTTP_COOKIE',
    'SERVER_NAME',
    'SERVER_PORT',
    'HTTP_X_AMZN_TRACE_ID'
]


def get_headers_for_api_context(request):
    return get_standard_headers(request.META, exclude=EXCLUDE_HEADERS)


def make_url_key():
    raw_key = urlsafe_b64encode(uuid.uuid4().bytes).decode()
    return raw_key.removesuffix("==")


@attr.s(kw_only=True, frozen=True, auto_attribs=True)
class ApiRequest:
    domain: str
    couch_user: CouchUser
    request_method: str
    user_agent: str
    data: str
    query: dict  # querystring key val pairs, vals are lists
    headers: dict
    request_id: str

    @classmethod
    def from_request(cls, request, request_id=None):
        if _request_too_large(request):
            raise GenericInboundUserError(_("Request exceeds the allowed size limit"))

        try:
            body = as_text(request.body)
        except UnicodeDecodeError:
            raise GenericInboundUserError(_("Unable to decode request body"))

        return cls(
            domain=request.domain,
            couch_user=request.couch_user,
            request_method=request.method,
            user_agent=request.META.get('HTTP_USER_AGENT'),
            data=body,
            query=dict(request.GET.lists()),
            headers=get_headers_for_api_context(request),
            request_id=request_id or uuid.uuid4().hex,
        )

    @classmethod
    def from_log(cls, log):
        return cls(
            domain=log.domain,
            couch_user=CouchUser.get_by_username(log.username),
            request_method=log.request_method,
            user_agent=log.request_headers.get('HTTP_USER_AGENT'),
            data=log.request_body,
            query=dict(QueryDict(log.request_query).lists()),
            headers=dict(log.request_headers),
            request_id=log.id
        )

    @cached_property
    def restore_user(self):
        return self.couch_user.to_ota_restore_user(
            self.domain, request_user=self.couch_user)


@attr.s(kw_only=True, frozen=True, auto_attribs=True)
class ApiResponse:
    """Data class for managing response data and producing HTTP responses.
    Override ``_get_http_response`` to return different HTTP response."""
    status: int
    internal_response: dict = None
    external_response: str = None
    content_type: str = None

    def get_http_response(self):
        if self.status == 204:
            return HttpResponse(status=204)  # no body for 204 (RFC 7230)
        return self._get_http_response()

    def _get_http_response(self):
        return HttpResponse(content=self.external_response, status=self.status, content_type=self.content_type)


def make_processing_attempt(response, request_log, is_retry=False):
    from corehq.motech.generic_inbound.models import ProcessingAttempt

    response_data = response.internal_response or {}
    case_ids = [c['case_id'] for c in response_data.get('cases', [])]
    ProcessingAttempt.objects.create(
        is_retry=is_retry,
        log=request_log,
        response_status=response.status,
        raw_response=response_data,
        external_response=response.external_response,
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

    def get_request_data():
        return ApiRequest.from_log(request_log)

    response = process_api_request(request_log.api, request_log.id, get_request_data)

    with transaction.atomic():
        request_log.status = RequestLog.Status.from_status_code(response.status)
        request_log.attempts += 1
        request_log.response_status = response.status
        request_log.save()
        make_processing_attempt(response, request_log, is_retry=True)


def process_api_request(api_model, request_id, get_request_data):
    try:
        backend_cls = api_model.backend_class
    except GenericInboundApiError as e:
        response = ApiResponse(status=500, internal_response={'error': str(e)})
    else:
        try:
            request_data = get_request_data()
        except GenericInboundUserError as e:
            response = backend_cls.get_basic_error_response(request_id, 400, str(e))
        else:
            response = backend_cls(api_model, request_data).run()
    return response


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


def log_api_request(request_id, api, request, response):
    if _request_too_large(request):
        body = '<truncated>'
    else:
        body = as_text(request.body)
    log = RequestLog.objects.create(
        id=request_id,
        domain=request.domain,
        api=api,
        status=RequestLog.Status.from_status_code(response.status),
        response_status=response.status,
        username=request.couch_user.username,
        request_method=request.method,
        request_query=request.META.get('QUERY_STRING'),
        request_body=body,
        request_headers=get_headers_for_api_context(request),
        request_ip=get_ip(request),
    )
    make_processing_attempt(response, log)


def _request_too_large(request):
    return int(request.META.get('CONTENT_LENGTH') or 0) > settings.MAX_UPLOAD_SIZE
