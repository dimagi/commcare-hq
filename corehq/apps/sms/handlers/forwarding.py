from corehq.apps.sms.models import (
    ForwardingRule, FORWARD_ALL, FORWARD_BY_KEYWORD,
)
from corehq.apps.sms.api import send_sms_with_backend

def forwarding_handler(v, text, msg):
    rules = ForwardingRule.view("sms/forwarding_rule",
        key=[v.domain], include_docs=True).all()
    text_words = text.upper().split()
    keyword_to_match = text_words[0] if len(text_words) > 0 else ""
    for rule in rules:
        matches_rule = False
        if rule.forward_type == FORWARD_ALL:
            matches_rule = True
        elif rule.forward_type == FORWARD_BY_KEYWORD:
            matches_rule = (keyword_to_match == rule.keyword.upper())
        
        if matches_rule:
            send_sms_with_backend(v.domain, "+%s" % v.phone_number, text,
                rule.backend_id)
            return True
    return False

