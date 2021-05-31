from enum import Enum

from corehq.apps.users.models_sql import HQLogEntry, UpdateDetails


class ModelAction(Enum):
    CREATE = HQLogEntry.CREATE
    UPDATE = HQLogEntry.UPDATE
    DELETE = HQLogEntry.DELETE


def log_model_change(domain, user, model_object, message=None, fields_changed=None, action=ModelAction.UPDATE,
                     can_skip_domain=False):
    """
    :param domain: domain where the update was initiated
    :param user: User making the change (couch user)
    :param model_object: The user being changed (couch user)
    :param message: Message text
    :param fields_changed: List of model field names that have
    :param action: Action on the model
    :param can_skip_domain: flag to allow domain less entry
    """
    if not domain and not can_skip_domain:
        raise ValueError("Please pass domain")

    if message is None and fields_changed is None:
        raise ValueError("One of 'message' or 'fields_changed' is required.")

    if message is not None and fields_changed is not None:
        raise ValueError("'message' and 'fields_changed' are mutually exclusive")

    if message is None:
        if not fields_changed:
            raise ValueError("'fields_changed' must not be empty")

        message = [{'changed': {'fields': fields_changed}}]

    return HQLogEntry.objects.create(
        domain=domain,
        object_type=model_object.doc_type,
        object_id=model_object.get_id,
        by_user_id=user.get_id,
        details=UpdateDetails.wrap({}),
        message=message,
        action_flag=action.value,
    )
