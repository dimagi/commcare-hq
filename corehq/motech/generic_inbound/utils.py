import json
import uuid
from base64 import urlsafe_b64encode

from django.http import QueryDict
from django.utils.translation import gettext as _

import attr

from casexml.apps.phone.xml import get_registration_element_data

from corehq.apps.auditcare.models import get_standard_headers
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.users.models import CouchUser
from corehq.motech.generic_inbound.exceptions import GenericInboundUserError


def make_url_key():
    raw_key = urlsafe_b64encode(uuid.uuid4().bytes).decode()
    return raw_key.removesuffix("==")


@attr.s(kw_only=True, frozen=True, auto_attribs=True)
class RequestData:
    domain: str
    couch_user: CouchUser  # Is this correct?
    request_method: str
    user_agent: str
    json: dict
    query: dict  # querystring key val pairs, vals are lists
    headers: dict

    @classmethod
    def from_request(cls, request):
        try:
            request_json = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GenericInboundUserError(_("Payload must be valid JSON"))
        return cls(
            domain=request.domain,
            couch_user=request.couch_user,
            request_method=request.method,
            user_agent=request.META.get('HTTP_USER_AGENT'),
            json=request_json,
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
            json=request_json,
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
            self.json,
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
