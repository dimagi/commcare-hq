from __future__ import absolute_import
from django.dispatch.dispatcher import receiver

from casexml.apps.case.signals import case_post_save
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.form_processor.signals import sql_case_post_save


@receiver([case_post_save, sql_case_post_save])
def clear_case_type_cache(sender, case, **kwargs):
    case_types = get_case_types_for_domain_es.get_cached_value(case.domain)
    if case_types != Ellipsis and case.type not in case_types:
        get_case_types_for_domain_es.clear(case.domain)
