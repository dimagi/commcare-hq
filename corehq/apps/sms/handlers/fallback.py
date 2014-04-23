from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms_to_verified_number

def fallback_handler(v, text, msg):
    domain_obj = Domain.get_by_name(v.domain, strict=True)
    if domain_obj.use_default_sms_response and domain_obj.default_sms_response:
        send_sms_to_verified_number(v, domain_obj.default_sms_response)
    return True

