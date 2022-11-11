import json
import uuid
from base64 import urlsafe_b64encode

from django.utils.translation import gettext as _

from casexml.apps.phone.xml import get_registration_element_data
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

    couch_user = request.couch_user
    restore_user = couch_user.to_ota_restore_user(request.domain, request_user=couch_user)

    query = dict(request.GET.lists())
    return get_evaluation_context(
        restore_user,
        request.method,
        query,
        dict(request.headers),
        body
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
