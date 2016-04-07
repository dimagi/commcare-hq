from __future__ import absolute_import
from couchdbkit import ResourceNotFound
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser


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
            'Location': Location,
        }.get(doc_type)

    for db in [user_db(), Location.get_db()]:
        try:
            owner_doc = db.get(owner_id)
        except ResourceNotFound:
            continue
        else:
            cls = _get_class(owner_doc['doc_type'])
            return cls.wrap(owner_doc) if cls else None
    return None


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
