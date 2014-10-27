from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import (
    send_sms_to_verified_number,
    MessageMetadata,
    add_msg_tags,
)
from corehq.apps.sms.models import WORKFLOW_DEFAULT


def fallback_handler(v, text, msg):
    domain_obj = Domain.get_by_name(v.domain, strict=True)
    default_workflow_meta = MessageMetadata(workflow=WORKFLOW_DEFAULT)
    if domain_obj.use_default_sms_response and domain_obj.default_sms_response:
        send_sms_to_verified_number(v, domain_obj.default_sms_response,
                                    metadata=default_workflow_meta)
    add_msg_tags(msg, default_workflow_meta)
    return True

