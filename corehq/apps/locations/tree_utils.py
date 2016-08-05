from collections import defaultdict


class TreeError(Exception):
    def __init__(self, msg, affected_nodes):
        self.affected_nodes = affected_nodes
        super(TreeError, self).__init__(msg)


class BadParentError(TreeError):
    pass


class CycleError(TreeError):
    pass


def _assert_has_valid_parents(nodes, root='TOP'):
    all_nodes = dict(nodes)

    # make sure all nodes have valid parents
    has_bad_parents = [node for node, parent in nodes
                       if parent != root and parent not in all_nodes]
    if has_bad_parents:
        raise BadParentError("Parent node not found", has_bad_parents)


def assert_no_cycles(nodes, root='TOP'):
    """
    'nodes' should be a list of (uid, parent_uid) tuples
    """

    all_nodes = dict(nodes)
    assert root not in all_nodes
    _assert_has_valid_parents(nodes, root)

    # for each node, walk up the tree, looking for any repeats
    def check(uid, visited):
        if uid in visited or uid == root:
            return False
        visited.add(uid)
        parent_uid = all_nodes[uid]
        if parent_uid != root:
            return check(parent_uid, visited)
        return True

    has_a_cycle = set()
    for uid, _ in nodes:
        if not check(uid, visited=set()):
            has_a_cycle.add(uid)

    if has_a_cycle:
        raise CycleError("Node parentage has a cycle", has_a_cycle)


def expansion_validators(nodes, root='TOP'):
    """
    Given a tree as a list of (uid, parent_uid), returns tuple of functions that return
    valid expand_from and expand_to options respectively.
    This assumes that tree validation is already done.
    """

    parent_of_child = dict(nodes)

    def valid_expand_from(uid):
        if uid == root:
            return [root]
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
