from __future__ import absolute_import

import uuid
from collections import defaultdict
from copy import copy, deepcopy
from xml.etree import cElementTree as ElementTree

from celery.task import task

from dimagi.utils.chunked import chunked
from casexml.apps.case.mock.case_block import IndexAttrs
from casexml.apps.phone.utils import MockDevice
from corehq.apps.es import CaseSearchES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.ota.utils import get_restore_user
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from soil import DownloadBase


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
    sync_result = device.sync()

    cases = {}
    new_case_ids = {}
    for case_id, case in sync_result.cases.iteritems():
        if case.case_type != "commcare-user":
            cases[case_id] = case
            new_case_ids[case_id] = [str(uuid.uuid4()) for _ in range(factor - 1)]

    total_cases = len(cases) * (factor - 1)
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

    graph = CaseGraph(cases)
    for old_case_id in graph.topological_sort():
        for explosion in range(factor - 1):
            new_case = copy(cases[old_case_id])

            new_case.create = True
            new_case.case_id = new_case_ids[old_case_id][explosion]
            new_case.update['cc_exploded_from'] = old_case_id
            new_case.update['cc_explosion_id'] = explosion_id
            new_case.index = {
                key: IndexAttrs(
                    i.case_type, new_case_ids[i.case_id][explosion], i.relationship
                ) for key, i in cases[old_case_id].index.iteritems()
            }
            progress += queue_case(ElementTree.tostring(new_case.as_xml()), queue, progress)

    if len(queue):
        submit_case_blocks(queue, domain, user_id=user_id, device_id="explode_cases")
        DownloadBase.set_progress(explode_case_task, total_cases, total_cases)

    return {'messages': [
        "Successfully created {} cases".format(total_cases),
        "Your explosion_id for this explosion is {}".format(explosion_id)
    ]}


class CaseGraph(object):
    def __init__(self, cases):
        self.graph = {}         # case indices
        self.inverse_graph = defaultdict(list)  # reverse indices
        self.roots = []

        for case_id, case in cases.iteritems():
            indices = [idx.case_id for idx in case.index.itervalues()]
            self.graph[case.case_id] = indices
            for index in indices:
                self.inverse_graph[index].append(case.case_id)

            if not indices:
                self.roots.append(case.case_id)

    def topological_sort(self):
        """returns all cases in topological order

        Using Kahn's algorithm from here:
        https://en.wikipedia.org/wiki/Topological_sorting

        Assumes there are no cycles in the graph
        """
        inverse_graph = self.inverse_graph
        graph = deepcopy(self.graph)
        L = []
        S = copy(self.roots)
        while len(S) > 0:
            n = S.pop()
            L.append(n)
            for m in inverse_graph[n]:
                graph[m].remove(n)
                if len(graph[m]) == 0:
                    S.append(m)
        return L


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

    completed = 0
    for ids in chunked(case_ids, 100):
        CaseAccessors(domain).soft_delete_cases(list(ids))
        if task:
            completed += len(ids)
            DownloadBase.set_progress(delete_exploded_case_task, completed, len(case_ids))
    return {'messages': ["Successfully deleted {} cases".format(len(case_ids))]}
