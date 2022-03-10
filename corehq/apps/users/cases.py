import numbers

from couchdbkit import ResourceNotFound

from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser, CouchUser, WebUser


def user_db():
    return CouchUser.get_db()


def get_owner_id(case):
    return case.owner_id or case.modified_by


def get_wrapped_owner(owner_id, support_deleted=False):
    """
    Returns the wrapped user or group object for a given ID, or None
    if the id isn't a known owner type.
    """
    if not owner_id:
        return None

    if isinstance(owner_id, numbers.Number):
        return None

    def _get_class(doc_type):
        return {
            'CommCareUser': CommCareUser,
            'WebUser': WebUser,
            'Group': Group,
        }.get(doc_type)

    def _get_deleted_class(doc_type):
        return {
            'Group-Deleted': Group,
        }.get(doc_type)

    try:
        return SQLLocation.objects.get(location_id=owner_id)
    except SQLLocation.DoesNotExist:
        pass

    try:
        owner_doc = user_db().get(owner_id)
    except ResourceNotFound:
        pass
    else:
        cls = _get_class(owner_doc['doc_type'])
        if support_deleted and cls is None:
            cls = _get_deleted_class(owner_doc['doc_type'])
        return cls.wrap(owner_doc) if cls else None

    return None
