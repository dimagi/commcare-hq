class TreeError(Exception):
    def __init__(self, msg, affected_nodes):
        self.affected_nodes = affected_nodes
        super(TreeError, self).__init__(msg)


def assert_no_cycles(nodes):
    """
    'nodes' should be a list of (uid, parent_uid) tuples
    """
    all_nodes = dict(nodes)

    # make sure all nodes have valid parents
    has_bad_parents = [node for node, parent in nodes
                       if parent and parent not in all_nodes]
    if has_bad_parents:
        raise TreeError("Parent node not found", has_bad_parents)

    # for each node, walk up the tree, looking for any repeats
    has_a_cycle = set()
    for uid, _ in nodes:
        visited = set()

        def check(uid_):
            if uid_ in visited:
                has_a_cycle.add(uid)  # original uid
                return
            visited.add(uid_)
            parent_uid = all_nodes[uid_]
            if parent_uid:
                check(parent_uid)

        check(uid)

    if has_a_cycle:
        raise TreeError("Node parentage has a cycle", has_a_cycle)
