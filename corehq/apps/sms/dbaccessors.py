from corehq.apps.sms.models import ForwardingRule


def get_forwarding_rules_for_domain(domain):
    return ForwardingRule.view(
        "sms/forwarding_rule",
        key=[domain],
        include_docs=True,
    ).all()
