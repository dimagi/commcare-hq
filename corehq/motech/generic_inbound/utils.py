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
    if couch_user.is_commcare_user():
        restore_user = couch_user.to_ota_restore_user(couch_user)
    elif couch_user.is_web_user():
        restore_user = couch_user.to_ota_restore_user(request.domain, couch_user)
    else:
        raise GenericInboundUserError(_("Unknown user type"))

    return get_evaluation_context(
        restore_user,
        request.method,
        request.META['QUERY_STRING'],
        dict(request.headers),
        body
    )


def get_evaluation_context(restore_user, method, query, headers, body):
    return EvaluationContext({
        'request_method': method,
        'query': query,
        'headers': headers,
        'body': body,
        'user': get_registration_element_data(restore_user)
    })
