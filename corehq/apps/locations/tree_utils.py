from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
from .const import ROOT_LOCATION_TYPE


class TreeError(Exception):
    def __init__(self, msg, affected_nodes):
        self.affected_nodes = affected_nodes
        super(TreeError, self).__init__(msg)


class BadParentError(TreeError):
    pass


class CycleError(TreeError):
    pass


def _assert_has_valid_parents(nodes):
    all_nodes = dict(nodes)

    # make sure all nodes have valid parents
    has_bad_parents = [node for node, parent in nodes
                       if parent != ROOT_LOCATION_TYPE and parent not in all_nodes]
    if has_bad_parents:
        raise BadParentError("Parent node not found", has_bad_parents)


def assert_no_cycles(nodes):
    """
    'nodes' should be a list of (uid, parent_uid) tuples
    Root parent should be indicated by ROOT_LOCATION_TYPE
    """

    all_nodes = dict(nodes)
    assert ROOT_LOCATION_TYPE not in all_nodes
    _assert_has_valid_parents(nodes)

    # for each node, walk up the tree, looking for any repeats
    def check(uid, visited):
        if uid in visited or uid == ROOT_LOCATION_TYPE:
            return False
        visited.add(uid)
        parent_uid = all_nodes[uid]
        if parent_uid != ROOT_LOCATION_TYPE:
            return check(parent_uid, visited)
        return True

    has_a_cycle = set()
    for uid, _ in nodes:
        if not check(uid, visited=set()):
            has_a_cycle.add(uid)

    if has_a_cycle:
        raise CycleError("Node parentage has a cycle", has_a_cycle)
