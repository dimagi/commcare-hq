from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class


def hq_group_export_configs_by_domain(domain):
    from corehq.apps.reports.models import HQGroupExportConfiguration
    return get_docs_in_domain_by_class(domain, HQGroupExportConfiguration)
