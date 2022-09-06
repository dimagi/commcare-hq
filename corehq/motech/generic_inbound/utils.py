import json
import uuid
from base64 import urlsafe_b64encode

from django.utils.translation import gettext as _

from corehq.apps.userreports.specs import EvaluationContext
from corehq.motech.generic_inbound.exceptions import GenericInboundUserError


def make_url_key():
    raw_key = urlsafe_b64encode(uuid.uuid4().bytes).decode()
    return raw_key.removesuffix("==")


def get_context_from_request(request):
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GenericInboundUserError(_("Payload must be valid JSON"))

    return get_evaluation_context(
        request.method,
        request.META['QUERY_STRING'],
        dict(request.headers),
        body
    )


def get_evaluation_context(method, query, headers, body):
    return EvaluationContext({
        'request_method': method,
        'query': query,
        'headers': headers,
        'body': body
    })
