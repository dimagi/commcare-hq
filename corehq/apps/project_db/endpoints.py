# Proof-of-concept endpoints to see how ProjectDB works as a case search backend.
from django.utils.translation import gettext as _

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.form_processor.models import CommCareCase

from .table_ddl import CaseTable, get_project_db_engine


def all_cases_of_type(helper, config):
    domain = helper.domain
    case_type = config.case_types[0]
    table = CaseTable(domain, case_type).reflect()
    if table is None:
        raise CaseSearchUserError(_("No ProjectDB table for case type '{}'").format(case_type))
    engine = get_project_db_engine()
    with engine.connect() as conn:
        rows = conn.execute(table.select().limit(1500)).fetchall()

    prop_columns = [col for col in table.columns if col.name.startswith('prop__')]
    return [
        CommCareCase(
            case_id=row['case_id'],
            domain=domain,
            type=case_type,
            name=row['case_name'],
            owner_id=row['owner_id'],
            opened_on=row['opened_on'],
            closed_on=row['closed_on'],
            closed=row['closed'],
            modified_on=row['modified_on'],
            server_modified_on=row['server_modified_on'],
            external_id=row['external_id'],
            # The column comment has the raw, untruncated property name
            case_json={col.comment: row[col.name] for col in prop_columns
                       if row[col.name]},
        ) for row in rows
    ]


STATIC_ENDPOINTS = {
    # name: function
    # These have to be ints, so picking an arbitrarily high number for now
    1_000_000: ('All Cases Of Type', all_cases_of_type),
}
