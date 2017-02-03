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


def expansion_validators(nodes):
    """
    Given a location type tree, this returns a tuple of functions that
    specify what a valid expand_from and sync_to are for a given node in the tree

    This assumes that tree validation is already done, passing in an unvalidated tree
    might result in unexpected behaviour.

    args:
        nodes: A list of tuples (uid, parent_uid) representing a location type tree structure

    returns:
        tuple: A tuple of two functions called valid_expand_from and valid_expand_to

        1st element of the tuple is a function called 'valid_expand_from'. It takes uid of a
        node in the tree and returns a list of valid 'expand_from' nodes for the given node

        2nd element of the tuple is a function called 'valid_expand_to', takes uid of a node
        in the tree and returns a list of valid 'sync_to' nodes for the given node

    """

    parent_of_child = dict(nodes)

    def valid_expand_from(uid):
        if uid == ROOT_LOCATION_TYPE:
            return [ROOT_LOCATION_TYPE]
        else:
            return [uid] + valid_expand_from(parent_of_child[uid])

    children_of_parent = defaultdict(list)
    for uid, parent_uid in nodes:
        children_of_parent[parent_uid].append(uid)

    def valid_expand_to(uid):
        children = children_of_parent[uid]
        if not children:
            return [uid]
        else:
            options = [uid]
            for child in children:
                options.extend(valid_expand_to(child))
            return options

    return valid_expand_from, valid_expand_to
