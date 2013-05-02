from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
from dimagi.utils.couch.database import iter_docs


def user_db():
    return CouchUser.get_db()

def get_owner_id(case):
    return case.owner_id if case.owner_id is not None else case.user_id

def get_wrapped_owner(owner_id):
    """
    Returns the wrapped user or group object for a given ID, or None
    if the id isn't a known owner type.
    """
    def _get_class(doc_type):
        return {
            'CommCareUser': CommCareUser,
            'WebUser': WebUser,
            'Group': Group,
        }.get(doc_type)

    owner_doc = user_db().get(owner_id)
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
