"""
This code lets you define hierarchies of users using groups and group metadata.
There's a dropdown report filter that uses this data to narrow down the users
included in a report. See the hsph-dev project for an example.
"""
from functools import partial
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.groups.models import Group


def get_group_by_user_type(domain, type):
    """
    A group's user type consists of its user_type metadata property.
    """
    return Group.view(
            'groups/by_user_type', include_docs=True, reduce=False,
            key=[domain, type])


def get_group_by_hierarchy_type(domain, type, owner_name=None):
    """
    A group's hierarchy type consists of its (owner_type, child_type)
    metadata.
    """
    view = partial(Group.view, 'groups/by_hierarchy_type', include_docs=True,
            reduce=False)
    key = [domain] + list(type)

    if owner_name:
        return view(key=key + [owner_name])
    else:
        return view(startkey=key, endkey=key + [{}])

@memoized
def get_hierarchy(domain, user_types, validate_types=False):
    """
    user_types -- a tuple of types corresponding to the levels of a tree of
        groups linked by their owner_type, child_type metadata and linked to
        users by their owner_name metadata (username).
        
        Example: ["supervisor", "team leader", "mobile worker"]

    validate_types -- whether to ensure that inner and leaf user nodes have
        the expected user types (by appearing in a group with the
        appropriate user_type metadata value)
    """
    # first get a dict keyed by the (owner_type, child_type) tuple (it
    # could just as well be a list in order) of dicts keyed by owner name
    # containing all groups that define this hierarchy type
    hierarchy_groups = {}

    for hierarchy_type in zip(user_types[:-1], user_types[1:]):
        groups = get_group_by_hierarchy_type(domain, hierarchy_type)
        groups_by_owner = {}
        for g in groups:
            try:
                groups_by_owner[g.metadata['owner_name']] = g
            except KeyError:
                # Group found with hierarchy type information but no owner
                # name
                pass

        hierarchy_groups[hierarchy_type] = groups_by_owner

    # then construct a tree given root users, looking up each user owning
    # group by hierarchy_type + username 
    def get_descendants(user, user_types):
        hierarchy_type = tuple(user_types[0:2])
        hierarchy_type_groups = hierarchy_groups[hierarchy_type]
        try:
            child_group = hierarchy_type_groups[user.raw_username]
            child_users = child_group.get_users()
        except KeyError:  # the user doesn't have a child group
            child_group = None
            child_users = []

        if validate_types and child_users:
            child_type = hierarchy_type[1]
            group = get_group_by_user_type(domain, child_type).first()
            if not group:
                raise Exception("No group found for type %s" % child_type)
            child_type_users = group.get_users()
            for child in child_users:
                if child not in child_type_users:
                    raise Exception("User and type don't match: %s, %s" % (
                        child.raw_username, child_type))
        ret = {
            "user": user,
            "child_group": child_group,
            "child_users": child_users,
        }
        
        if len(user_types) >= 3:
            user_types = user_types[1:]
            ret["descendants"] = [
                get_descendants(c, user_types) for c in child_users]
        return ret

    root_group = get_group_by_user_type(domain, user_types[0]).first()
    if not root_group:
        raise Exception("Unknown user type: %s" % user_types[0])

    root_users = root_group.get_users()

    return [get_descendants(u, user_types) for u in root_users]


def get_user_data_from_hierarchy(domain, user_types, root_user_id=None):
    import collections
    root_nodes = get_hierarchy(domain, user_types)

    if root_user_id:
        q = collections.deque(root_nodes)
        root_node = None
        while q:
            node = q.popleft()
            if node['user']._id == root_user_id:
                root_node = node
                break
            q.extend(node.get('descendants', []))
        if not root_node:
            raise Exception("Invalid user id %r for hierarchy %r" % (
                    root_user_id, user_types))
        root_nodes = [root_node]

    # this is a minor hack, could probably make the node structure better and
    # have leaf nodes for each leaf child, and add a parent reference
    user_parent_map = {}

    def get_leaf_users(node):
        current_user = node['user']
        for child in node['child_users']:
            user_parent_map[child._id] = current_user

        descendants = node.get('descendants')
        if descendants:
            leaves = []
            for d in descendants:
                leaves.extend(get_leaf_users(d))
        else:
            leaves = node['child_users']
        return leaves

    leaf_nodes = []
    for root_node in root_nodes:
        leaf_nodes.extend(get_leaf_users(root_node))

    return {
        'leaf_user_ids': [n._id for n in leaf_nodes],
        'user_parent_map': user_parent_map,
    }
