from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.motech.openmrs.models import OpenmrsImporter
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.util.quickcache import quickcache


@quickcache(['domain_name'])
def get_openmrs_importers_by_domain(domain_name):
    return OpenmrsImporter.view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'OpenmrsImporter', None],
        include_docs=True,
        reduce=False,
    ).all()


@quickcache(['domain_name'])
def get_openmrs_repeaters_by_domain(domain_name):
    return OpenmrsRepeater.view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'OpenmrsRepeater', None],
        include_docs=True,
        reduce=False,
    ).all()
