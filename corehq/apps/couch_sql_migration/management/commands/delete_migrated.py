"""
Finds and deletes forms and cases created during an aborted migration
"""
import datetime

from django.db.models import Q

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import validate_phone_datetime
from casexml.apps.case.xform import get_case_ids_from_form
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch

from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
)
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.sql_db.util import paginate_query_across_partitioned_databases


# domain = "infomovel-pepfar"
# src_domain = "infomovel"
# start_datetime = datetime.datetime(2019, 9, 3,  21, 16, tzinfo=datetime.timezone.utc)
# end_datetime = datetime.datetime(2019, 9, 4,  6, 20, tzinfo=datetime.timezone.utc)
# a_month_ago = datetime.datetime(2019, 8, 3,  0, 0)


def delete_migrated_forms():
    form_ids, case_ids = get_migrated_forms(domain, start_datetime, end_datetime)
    CaseAccessorSQL.hard_delete_cases(domain, list(case_ids))
    FormAccessorSQL.hard_delete_forms(domain, list(form_ids),
                                      delete_attachments=True)


def get_migrated_forms(domain, start_datetime, end_datetime):
    form_ids = set()
    case_ids = set()

    for form in iter_forms_by_modified_on(domain, start_datetime, end_datetime):
        from_domain = get_auth_context_domain(form)
        if from_domain and from_domain != src_domain:
            continue
        if from_domain is None:
            if not is_old(form):
                continue

        form_ids.add(form.form_id)
        form_case_ids = get_case_ids_from_form(form)
        case_ids.update(form_case_ids)

    return form_ids, case_ids


def iter_forms_by_modified_on(domain, start_datetime, end_datetime):
    # cf. corehq/form_processor/backends/sql/dbaccessors.py:390
    return paginate_query_across_partitioned_databases(
        XFormInstanceSQL,
        Q(domain=domain,
          server_modified_on__gt=start_datetime,
          server_modified_on__lte=end_datetime),
        load_source='find_migrated_forms'
    )


def get_auth_context_domain(form):
    try:
        return form.auth_context["domain"]
    except (AttributeError, KeyError):
        return None


def is_old(form):
    received_on = validate_phone_datetime(form.received_on)
    return received_on < a_month_ago


# def get_migrated_cases(domain, start_datetime, end_datetime):
#     # DO NOT USE FOR DELETING: THESE COULD BE CASE UPDATES FOR CASES
#     # MIGRATED FROM OTHER DOMAINS
#     # e.g. 6e7e2922-1d54-40d8-84af-77e622ae6ccf from infomovel-ccs
#     case_ids = set()
#     form_ids = set()
#
#     for case in iter_cases_by_modified_on(domain, start_datetime, end_datetime):
#         if CaseAccessorCouch.case_exists(case.case_id):
#             case_ids.add(case.case_id)
#             form_ids.update(CaseAccessorCouch.get_case_xform_ids(case.case_id))
#
#     return case_ids, form_ids


def iter_cases_by_modified_on(domain, start_datetime, end_datetime):
    return paginate_query_across_partitioned_databases(
        CommCareCaseSQL,
        Q(domain=domain,
          server_modified_on__gt=start_datetime,
          server_modified_on__lte=end_datetime),
        load_source='find_migrated_forms'
    )
