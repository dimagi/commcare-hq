from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.mock import CaseFactory
from contextlib import contextmanager
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.utils.general import should_use_sql_backend


@contextmanager
def create_case(domain, case_type, **kwargs):
    case = CaseFactory(domain).create_case(case_type=case_type, **kwargs)

    try:
        yield case
    finally:
        if should_use_sql_backend(domain):
            CaseAccessorSQL.hard_delete_cases(domain, [case.case_id])
        else:
            case.delete()


def create_empty_rule(domain, workflow):
    return AutomaticUpdateRule.objects.create(
        domain=domain,
        name='test',
        case_type='person',
        active=True,
        deleted=False,
        filter_on_server_modified=False,
        server_modified_boundary=None,
        migrated=True,
        workflow=workflow,
    )
