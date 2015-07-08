from corehq.apps.sms.models import ForwardingRule


def get_forwarding_rules_for_domain(domain):
    return ForwardingRule.view(
        "domain/docs",
        startkey=[domain, 'ForwardingRule'],
        endkey=[domain, 'ForwardingRule', {}],
        include_docs=True,
        reduce=False,
    ).all()
