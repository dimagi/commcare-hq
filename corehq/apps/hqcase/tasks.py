from __future__ import absolute_import
import uuid
from copy import copy, deepcopy
from collections import defaultdict

from celery.task import task
from soil import DownloadBase
from xml.etree import cElementTree as ElementTree

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.hqcase.utils import submit_case_blocks, make_creating_casexml
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.ota.utils import get_restore_user
from casexml.apps.phone.tests.utils import MockDevice
from casexml.apps.case.mock.case_block import IndexAttrs


@task
def explode_case_task(user_id, domain, factor):
    explode_cases(user_id, domain, factor, explode_case_task)


def explode_cases(domain, user_id, factor, task=None):
    user = CommCareUser.get_by_user_id(user_id, domain)
    messages = list()
    if task:
        DownloadBase.set_progress(explode_case_task, 0, 0)
    count = 0

    old_to_new = dict()
    child_cases = list()
    accessor = CaseAccessors(domain)

    case_ids = accessor.get_case_ids_by_owners(user.get_owner_ids(), closed=False)
    cases = accessor.iter_cases(case_ids)

    # copy parents
    for case in cases:
        # skip over user as a case
        if case.type == USERCASE_TYPE:
            continue
        # save children for later
        if case.indices:
            child_cases.append(case)
            continue
        old_to_new[case.case_id] = list()
        for i in range(factor - 1):
            new_case_id = uuid.uuid4().hex
            # add new parent ids to the old to new id mapping
            old_to_new[case.case_id].append(new_case_id)
            submit_case(case, new_case_id, domain, "explode_cases[copy parents]")
            count += 1
            if task:
                DownloadBase.set_progress(explode_case_task, count, 0)

    max_iterations = len(child_cases) ** 2
    iterations = 0
    while len(child_cases) > 0:
        if iterations > max_iterations:
            raise Exception('cases had inconsistent references to each other')
        iterations += 1
        # take the first case
        case = child_cases.pop(0)
        can_process = True
        parent_ids = dict()

        for index in case.indices:
            ref_id = index.referenced_id
            # if the parent hasn't been processed
            if ref_id not in old_to_new.keys():
                # append it to the backand break out
                child_cases.append(case)
                can_process = False
                break
            # update parent ids that this case needs
            parent_ids.update({ref_id: old_to_new[ref_id]})
        # keep processing
        if not can_process:
            continue

        old_to_new[case.case_id] = list()
        for i in range(factor - 1):
            # grab the parents for this round of exploding
            parents = {k: v[i] for k, v in parent_ids.items()}
            new_case_id = uuid.uuid4().hex
            old_to_new[case.case_id].append(new_case_id)
            submit_case(case, new_case_id, domain, "explode_cases", parents)
            count += 1
            if task:
                DownloadBase.set_progress(explode_case_task, count, 0)

    messages.append("All of %s's cases were exploded by a factor of %d" % (user.raw_username, factor))

    return {'messages': messages}


def submit_case(case, new_case_id, domain, source, new_parent_ids=dict()):
    device_id = __name__ + "." + source
    case_block, attachments = make_creating_casexml(domain, case, new_case_id, new_parent_ids)
    submit_case_blocks(case_block, domain, attachments=attachments, device_id=device_id)


def explode_cases_2(domain, user_id, factor):
    queue = []

    def queue_case(new_case, queue):
        queue.append(new_case)
        if len(queue) >= 500:   # submit 500 cases at a time
            submit_case_blocks(queue, domain, user_id=user_id, device_id="explode_cases")
            del queue[:]

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
            queue_case(ElementTree.tostring(new_case.as_xml()), queue)

    if len(queue):
        submit_case_blocks(queue, domain, user_id=user_id, device_id="explode_cases")


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

    def get_paths_to_root(self, case_id):
        """find all paths to the root node
        """
        def paths_to_root(case_id, path):
            path = path + [case_id]
            if case_id not in self.graph:
                return [path]
            if not self.graph[case_id]:  # we made it to the top
                return [path]
            paths = []
            for node in self.graph[case_id]:
                if node not in path:
                    newpaths = paths_to_root(node, path)
                    for newpath in newpaths:
                        paths.append(newpath)
            return paths

        return paths_to_root(case_id, [])

    def get_ancestors(self, case_id, include_self=False):
        paths = self.get_paths_to_root(case_id)
        ancestors = set()
        for path in paths:
            ancestors |= set(path)
        if not include_self:
            ancestors.remove(case_id)

        return ancestors

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
