from __future__ import absolute_import
from __future__ import unicode_literals
import warnings
from casexml.apps.case.models import CommCareCase
from corehq.apps.es import CaseES


def get_number_of_cases_in_domain_of_type(domain, case_type):
    warnings.warn(
        'get_number_of_cases_in_domain_of_type works off couch '
        'and thus is not suitable for use on SQL domains', DeprecationWarning)
    type_key = [case_type] if case_type else []
    row = CommCareCase.get_db().view(
        "case_types_by_domain/view",
        startkey=[domain] + type_key,
        endkey=[domain] + type_key + [{}],
        reduce=True,
    ).one()
    return row["value"] if row else 0


def get_number_of_cases_in_domain(domain):
    return CaseES().domain(domain).size(0).run().total
