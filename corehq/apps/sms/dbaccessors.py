from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.models import ForwardingRule


def get_forwarding_rules_for_domain(domain):
    return ForwardingRule.view(
        "by_domain_doc_type_date/view",
        startkey=[domain, 'ForwardingRule'],
        endkey=[domain, 'ForwardingRule', {}],
        include_docs=True,
        reduce=False,
    ).all()
