import uuid

from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance

DOMAIN = "export-file-domain"
DEFAULT_USER = "user1"
DEFAULT_CASE_TYPE = "test-case-type"
DEFAULT_CASE_NAME = "a case"
DEFAULT_APP_ID = "test-app-id"
DEFAULT_XMLNS = "test-xmlns"


def new_case(domain=DOMAIN, user_id=DEFAULT_USER, owner_id=DEFAULT_USER,
             type=DEFAULT_CASE_TYPE, name=DEFAULT_CASE_NAME,
             closed=False, **kwargs):
    kwargs["_id"] = kwargs.get("_id", uuid.uuid4().hex)
    return CommCareCase(
        domain=domain,
        user_id=user_id,
        owner_id=owner_id,
        type=type,
        name=name,
        closed=closed,
        **kwargs
    )


def new_form(domain=DOMAIN, app_id=DEFAULT_APP_ID, xmlns=DEFAULT_XMLNS, **kwargs):
    kwargs["_id"] = kwargs.get("_id", uuid.uuid4().hex)
    return XFormInstance(
        domain=domain,
        app_id=app_id,
        xmlns=xmlns,
        **kwargs
    )
