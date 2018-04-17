from __future__ import absolute_import
from __future__ import unicode_literals
import six

import uuid
from collections import defaultdict
from copy import copy

from celery.task import task

from dimagi.utils.chunked import chunked
from casexml.apps.case.mock.case_block import IndexAttrs
from casexml.apps.phone.const import LIVEQUERY
from casexml.apps.phone.utils import MockDevice
from corehq.apps.es import CaseSearchES
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.ota.utils import get_restore_user
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from soil import DownloadBase
from six.moves import range


@task
def explode_case_task(domain, user_id, factor):
    return explode_cases(domain, user_id, factor, explode_case_task)


def explode_cases(domain, user_id, factor, task=None):
    if task:
        DownloadBase.set_progress(explode_case_task, 0, 0)

    explosion_id = str(uuid.uuid4())

    couch_user = CommCareUser.get_by_user_id(user_id, domain)
    restore_user = get_restore_user(domain, couch_user, None)
    device = MockDevice(restore_user.project, restore_user, {"overwrite_cache": True, "case_sync": LIVEQUERY})
    sync_result = device.restore()

    cases = {}
    new_case_ids = {}
    for case_id, case in six.iteritems(sync_result.cases):
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

    for old_case_id in topological_sort_cases(cases):
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
                ) for key, i in six.iteritems(cases[old_case_id].index)
            }
            progress += queue_case(new_case.as_string(), queue, progress)

            for ledger in sync_result.ledgers.get(old_case_id, []):
                new_ledger = copy(ledger)
                new_ledger.entity_id = new_case_id
                total_ledgers += 1
                queue_case(new_ledger.as_string(), queue, progress)

    if len(queue):
        submit_case_blocks(queue, domain, user_id=user_id, device_id="explode_cases")
        DownloadBase.set_progress(explode_case_task, total_cases, total_cases)

    return {'messages': [
        "Successfully created {} cases".format(total_cases),
        "Successfully created {} ledgers".format(total_ledgers),
        "Your explosion_id for this explosion is {}".format(explosion_id)
    ]}


def topological_sort_cases(cases):
    """returns all cases in topological order

    Using Kahn's algorithm from here:
    https://en.wikipedia.org/wiki/Topological_sorting
    L = sorted_ids
    roots = S
    root_id = n
    case_id = m

    """
    graph = {}
    inverse_graph = defaultdict(list)
    roots = []

    # compile graph
    for case_id, case in six.iteritems(cases):
        graph[case.case_id] = indices = []
        for index in six.itervalues(case.index):
            indices.append(index.case_id)
            inverse_graph[index.case_id].append(case.case_id)
        if not indices:
            roots.append(case.case_id)

    # sort graph
    sorted_ids = []
    while roots:
        root_id = roots.pop()
        sorted_ids.append(root_id)
        for case_id in sorted(inverse_graph[root_id]):
            graph[case_id].remove(root_id)
            if not graph[case_id]:
                roots.append(case_id)

    for indices in six.itervalues(graph):
        if indices:
            raise ValueError("graph has cycles")

    return sorted_ids


@task
def delete_exploded_case_task(domain, explosion_id):
    return delete_exploded_cases(domain, explosion_id, delete_exploded_case_task)


def delete_exploded_cases(domain, explosion_id, task=None):
    if task:
        DownloadBase.set_progress(delete_exploded_case_task, 0, 0)
    query = (CaseSearchES()
             .domain(domain)
             .case_property_query("cc_explosion_id", explosion_id))
    case_ids = query.values_list('_id', flat=True)
    if task:
        DownloadBase.set_progress(delete_exploded_case_task, 0, len(case_ids))

    case_accessor = CaseAccessors(domain)
    form_accessor = FormAccessors(domain)
    ledger_accessor = LedgerAccessorSQL
    deleted_form_ids = set()
    num_deleted_ledger_entries = 0

    for id in case_ids:
        ledger_form_ids = {tx.form_id for tx in ledger_accessor.get_ledger_transactions_for_case(id)}
        for form_id in ledger_form_ids:
            ledger_accessor.delete_ledger_transactions_for_form([id], form_id)
        num_deleted_ledger_entries += ledger_accessor.delete_ledger_values(id)

        new_form_ids = set(case_accessor.get_case_xform_ids(id)) - deleted_form_ids
        form_accessor.soft_delete_forms(list(new_form_ids))
        deleted_form_ids |= new_form_ids

    completed = 0
    for ids in chunked(case_ids, 100):
        case_accessor.soft_delete_cases(list(ids))
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
