from enum import Enum

from corehq.apps.users.models_sql import HQLogEntry, UpdateDetails


class ModelAction(Enum):
    CREATE = HQLogEntry.CREATE
    UPDATE = HQLogEntry.UPDATE
    DELETE = HQLogEntry.DELETE


def log_model_change(domain, user, model_object, message=None, fields_changed=None, action=ModelAction.UPDATE,
                     can_skip_domain=False, changed_via=None):
    """
    :param domain: domain where the update was initiated
    :param user: User making the change (couch user) or SYSTEM_USER_ID
    :param model_object: The user being changed (couch user)
    :param message: Optional Message text
    :param fields_changed: List of model field names that have
    :param action: Action on the model
    :param can_skip_domain: flag to allow domain less entry
    :param changed_via: changed via medium i.e API/Web
    """
    from corehq.apps.users.util import SYSTEM_USER_ID

    if not domain and not can_skip_domain and user != SYSTEM_USER_ID:
        raise ValueError("Please pass domain")

    if action == ModelAction.UPDATE:
        if not fields_changed:
            raise ValueError("'fields_changed' is required for update.")

    return HQLogEntry.objects.create(
        domain=domain,
        object_type=model_object.doc_type,
        object_id=model_object.get_id,
        by_user_id=SYSTEM_USER_ID if user == SYSTEM_USER_ID else user.get_id,
        details=UpdateDetails.wrap({
            'changes': _get_change_details(model_object, action, fields_changed),
            'changed_via': changed_via,
        }),
        message=message,
        action=action.value,
    )


def _get_change_details(couch_user, action, fields_changed):
    # ToDo: return updates
    return {}
