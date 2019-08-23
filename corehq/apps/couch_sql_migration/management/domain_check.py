from corehq.form_processor.interfaces import dbaccessors
from casexml.apps.case.models import CommCareCase
import random
from corehq.util.log import with_progress_bar
from corehq.apps.couch_sql_migration.diff import filter_case_diffs
from corehq.apps.tzmigration.timezonemigration import json_diff
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from corehq.form_processor.backends.couch.update_strategy import CouchCaseUpdateStrategy
from six.moves import range


def check_domain(domain, num_cases=1000, randomization=100):
    form_db = dbaccessors.FormAccessors(domain)

    case_iterator = CouchViewChangeProvider(
        couch_db=CommCareCase.get_db(),
        view_name='by_domain_doc_type_date/view',
        view_kwargs={
            'startkey': [domain, 'CommCareCase'],
            'endkey': [domain, 'CommCareCase', {}],
            'include_docs': False,
        }
    ).iter_all_changes()

    for i in with_progress_bar(range(0, num_cases), oneline=False):
        skips = random.randint(1, randomization)
        for _ in range(0, skips):
            case = next(case_iterator)

        current_case = CommCareCase(case.get_document())
        case_id, diffs = is_problem_case(current_case, form_db)
        if case_id:
            print("%s: diffs" % case_id)
            for diff in diffs:
                print(diff)


def is_problem_case(case, form_db):
    orig_case_json = case.to_json()
    sorted_actions = sorted(case.actions, key=lambda x: x.server_date)
    sorted_form_ids = [action.xform_id for action in sorted_actions]
    if sorted_form_ids != case.xform_ids:
        rebuild_case_from_sorted_actions(case, sorted_actions)
        rebuilt_case_json = case.to_json()
        diffs = json_diff(orig_case_json, rebuilt_case_json)
        diffs = filter_case_diffs(
            orig_case_json, rebuilt_case_json, diffs
        )
        diffs = [diff for diff in diffs if diff.path[0] not in ['actions', 'xform_ids']]
        diffs = [d for d in diffs if d.old_value or d.new_value]
        if diffs:
            return (case.case_id, diffs)
    return False, None


def rebuild_case_from_sorted_actions(case, sorted_actions):
    strategy = CouchCaseUpdateStrategy(case)
    strategy.reset_case_state()
    case.xform_ids = []
    case.actions = [a for a in sorted_actions if not a.deprecated]
    for a in case.actions:
        strategy._apply_action(a, None)
    case.xform_ids = []
    for a in case.actions:
        if a.xform_id and a.xform_id not in case.xform_ids:
            case.xform_ids.append(a.xform_id)
