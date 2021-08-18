from contextlib import contextmanager

from casexml.apps.case.mock import CaseFactory

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL


@contextmanager
def create_case(domain, case_type, **kwargs):
    case = CaseFactory(domain).create_case(case_type=case_type, **kwargs)

    try:
        yield case
    finally:
        CaseAccessorSQL.hard_delete_cases(domain, [case.case_id])


def create_empty_rule(domain, workflow, case_type='person'):
    return AutomaticUpdateRule.objects.create(
        domain=domain,
        name='test',
        case_type=case_type,
        active=True,
        deleted=False,
        filter_on_server_modified=False,
        server_modified_boundary=None,
        workflow=workflow,
    )
