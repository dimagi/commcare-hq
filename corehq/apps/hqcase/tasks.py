import uuid
from collections import defaultdict
from copy import copy

from toposort import toposort_flatten

from casexml.apps.case.mock.case_block import IndexAttrs
from casexml.apps.phone.utils import MockDevice
from dimagi.utils.chunked import chunked
from soil import DownloadBase

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.celery import task
from corehq.apps.es import CaseSearchES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.ota.utils import get_restore_user
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.models import CommCareCase, XFormInstance


@task
def explode_case_task(domain, user_id, factor):
    return explode_cases(domain, user_id, factor, explode_case_task)


def explode_cases(domain, user_id, factor, task=None):
    if task:
        DownloadBase.set_progress(explode_case_task, 0, 0)

    explosion_id = str(uuid.uuid4())

    couch_user = CommCareUser.get_by_user_id(user_id, domain)
    restore_user = get_restore_user(domain, couch_user, None)
    device = MockDevice(restore_user.project, restore_user, {"overwrite_cache": True})
    sync_result = device.restore()

    cases = {}
    new_case_ids = {}
    for case_id, case in sync_result.cases.items():
        if case.case_type != USERCASE_TYPE:
            cases[case_id] = case
            new_case_ids[case_id] = [str(uuid.uuid4()) for _ in range(factor - 1)]

    total_cases = len(cases) * (factor - 1)
    total_ledgers = 0
    if task:
        DownloadBase.set_progress(explode_case_task, 0, total_cases)

    queue = []
    progress = 0

    def queue_case(new_case, queue, progress):
        queue.append(new_case)
        if len(queue) >= 500:   # submit 500 cases at a time
            submit_case_blocks(queue, domain, user_id=user_id, device_id="explode_cases")
            progress += len(queue)
            if task:
                DownloadBase.set_progress(explode_case_task, progress, total_cases)
            del queue[:]
        return progress

    for old_case_id in reversed(topological_sort_case_blocks(cases)):
        for explosion in range(factor - 1):
            new_case = copy(cases[old_case_id])
            new_case_id = new_case_ids[old_case_id][explosion]

            new_case.create = True
            new_case.case_id = new_case_id
            new_case.update['cc_exploded_from'] = old_case_id
            new_case.update['cc_explosion_id'] = explosion_id
            new_case.index = {
                key: IndexAttrs(
                    i.case_type, new_case_ids[i.case_id][explosion], i.relationship
                ) for key, i in cases[old_case_id].index.items()
            }
            progress += queue_case(new_case.as_text(), queue, progress)

            for ledger in sync_result.ledgers.get(old_case_id, []):
                new_ledger = copy(ledger)
                new_ledger.entity_id = new_case_id
                total_ledgers += 1
                queue_case(new_ledger.as_string().decode('utf-8'), queue, progress)

    if len(queue):
        submit_case_blocks(queue, domain, user_id=user_id, device_id="explode_cases")
        DownloadBase.set_progress(explode_case_task, total_cases, total_cases)

    return {'messages': [
        "Successfully created {} cases".format(total_cases),
        "Successfully created {} ledgers".format(total_ledgers),
        "Your explosion_id for this explosion is {}".format(explosion_id)
    ]}


def topological_sort_case_blocks(cases):
    """returns a list of case IDs in topological order according to their
    case indices
    """
    tree = defaultdict(set)
    for case_id, case in cases.items():
        tree[case_id]  # prime for case
        for index in case.index.values():
            tree[index.case_id].add(case_id)
    return toposort_flatten(tree)


@task
def delete_exploded_case_task(domain, explosion_id):
    return delete_exploded_cases(domain, explosion_id, delete_exploded_case_task)


def delete_exploded_cases(domain, explosion_id, task=None):
    if not explosion_id:
        raise Exception("explosion_id is falsy, aborting rather than deleting all cases")
    if task:
        DownloadBase.set_progress(delete_exploded_case_task, 0, 0)
    query = (CaseSearchES()
             .domain(domain)
             .case_property_query("cc_explosion_id", explosion_id))
    case_ids = query.values_list('_id', flat=True)
    if task:
        DownloadBase.set_progress(delete_exploded_case_task, 0, len(case_ids))

    ledger_accessor = LedgerAccessorSQL
    deleted_form_ids = set()
    num_deleted_ledger_entries = 0

    for id in case_ids:
        ledger_form_ids = {tx.form_id for tx in ledger_accessor.get_ledger_transactions_for_case(id)}
        for form_id in ledger_form_ids:
            ledger_accessor.delete_ledger_transactions_for_form([id], form_id)
        num_deleted_ledger_entries += ledger_accessor.delete_ledger_values(id)

        new_form_ids = set(CommCareCase.objects.get_case_xform_ids(id)) - deleted_form_ids
        XFormInstance.objects.soft_delete_forms(domain, list(new_form_ids))
        deleted_form_ids |= new_form_ids

    completed = 0
    for ids in chunked(case_ids, 100):
        CommCareCase.objects.soft_delete_cases(domain, list(ids))
        if task:
            completed += len(ids)
            DownloadBase.set_progress(delete_exploded_case_task, completed, len(case_ids))
    return {
        'messages': [
            "Successfully deleted {} cases".format(len(case_ids)),
            "Successfully deleted {} forms".format(len(deleted_form_ids)),
            "Successfully deleted {} ledgers".format(num_deleted_ledger_entries),
        ]
    }
