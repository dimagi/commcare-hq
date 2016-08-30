from couchdbkit import ResourceNotFound

from corehq.toggles import NAMESPACE_DOMAIN
from toggle.models import Toggle
from toggle.shortcuts import update_toggle_cache


def move_toggles(from_toggle_id, to_toggle_id):
    """
    Moves all enabled items from one toggle to another.
    """
    try:
        from_toggle = Toggle.get(from_toggle_id)
    except ResourceNotFound:
        # if no source found this is a noop
        return
    try:
        to_toggle = Toggle.get(to_toggle_id)
    except ResourceNotFound:
        to_toggle = Toggle(slug=to_toggle_id, enabled_users=[])

    for item in from_toggle.enabled_users:
        if item not in to_toggle.enabled_users:
            to_toggle.enabled_users.append(item)
            namespace = None
            if item.startswith(NAMESPACE_DOMAIN):
                item = item.split(":")[1]
                namespace = NAMESPACE_DOMAIN
            update_toggle_cache(to_toggle_id, item, True, namespace=namespace)

    to_toggle.save()
    from_toggle.delete()
