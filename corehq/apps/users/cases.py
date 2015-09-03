from __future__ import absolute_import
from couchdbkit import ResourceNotFound
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
from corehq.apps.hqcase.utils import assign_cases


def user_db():
    return CouchUser.get_db()


def get_owner_id(case):
    return case.owner_id or case.user_id


def get_wrapped_owner(owner_id):
    """
    Returns the wrapped user or group object for a given ID, or None
    if the id isn't a known owner type.
    """
    if not owner_id:
        return None

    def _get_class(doc_type):
        return {
            'CommCareUser': CommCareUser,
            'WebUser': WebUser,
            'Group': Group,
        }.get(doc_type)

    try:
        owner_doc = user_db().get(owner_id)
    except ResourceNotFound:
        return None
    cls = _get_class(owner_doc['doc_type'])
    return cls.wrap(owner_doc) if cls else None


def get_owning_users(owner_id):
    """
    Given an owner ID, get a list of the owning users, regardless of whether
    it's a user or group.
    """
    owner = get_wrapped_owner(owner_id)
    if not owner:
        return []
    elif isinstance(owner, Group):
        return owner.get_users()
    else:
        return [owner]


def reconcile_ownership(case, user, recursive=True, existing_groups=None):
    """
    Reconciles ownership of a case (and optionally its subcases) by the following rules:
    0. If the case is owned by the user, do nothing.
    1. If the case has no owner, make the user the owner.
    2. If the case has an owner that is a user create a new case sharing group,
       add that user and the new user to the case sharing group make the group the owner.
    3. If the case has an owner that is a group, and the user is in the group, do nothing.
    4. If the case has an owner that is a group, and the user is not in the group,
       add the user to the group and the leave the owner untouched.

    Will recurse through subcases if asked to.
    Existing groups, if specified, will be checked first for satisfying the ownership
    criteria in scenario 2 before creating a new group (this is mainly used by the
    recursive calls)
    """
    existing_groups = {} if existing_groups is None else existing_groups

    def _get_matching_group(groups, user_ids):
        """
        Given a list of groups and user_ids, returns any group that contains
        all of the user_ids, or None if no match is found.
        """
        for group in groups:
            if all(user in group.users for user in user_ids):
                return group
        return None

    owner = get_wrapped_owner(get_owner_id(case))
    if owner and owner._id == user._id:
        pass
    elif owner is None:
        # assign to user
        _assign_case(case, user._id, user)
    elif isinstance(owner, CommCareUser):
        needed_owners = [owner._id, user._id]
        matched = _get_matching_group(existing_groups.values(), needed_owners)
        if matched:
            _assign_case(case, matched._id, user)
        else:
            new_group = Group(
                domain=case.domain,
                name="{case} Owners (system)".format(case=case.name or case.type),
                users=[owner._id, user._id],
                case_sharing=True,
                reporting=False,
                metadata={
                    'hq-system': True,
                }
            )
            new_group.save()
            existing_groups[new_group._id] = new_group
            _assign_case(case, new_group._id, user)
    else:
        assert isinstance(owner, Group)
        if user._id not in owner.users:
            owner.users.append(user._id)
            owner.save()
        existing_groups[owner._id] = owner

    if recursive:
        for subcase in case.get_subcases():
            reconcile_ownership(subcase, user, recursive, existing_groups)


def _assign_case(case, new_owner_id, acting_user):
    return assign_cases([case], new_owner_id, acting_user)
