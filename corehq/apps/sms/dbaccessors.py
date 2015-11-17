from corehq.apps.sms.models import ForwardingRule


def get_forwarding_rules_for_domain(domain):
    return ForwardingRule.view(
        "by_domain_doc_type/view",
        key=[domain, 'ForwardingRule'],
        include_docs=True,
        reduce=False,
    ).all()
