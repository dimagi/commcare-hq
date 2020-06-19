from django.contrib.admin.options import get_content_type_for_model
from django.utils.encoding import force_text


def log_model_change(user, model_object, message=None, fields_changed=None, is_create=False):
    """
    :param user: User making the change (couch user or django user)
    :param model_object: The object being changed (must be a Django model)
    :param message: Message text
    :param fields_changed: List of model field names that have changed
    """
    from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
    from corehq.apps.users.models import CouchUser
    if isinstance(user, CouchUser):
        user = user.get_django_user()

    if message is None and fields_changed is None:
        raise ValueError("One of 'message' or 'fields_changed' is required.")

    if message is not None and fields_changed is not None:
        raise ValueError("'message' and 'fields_changed' are mutually exclusive")

    if message is None:
        if not fields_changed:
            raise ValueError("'fields_changed' must not be empty")

        message = {'changed': {'fields': fields_changed}}

    return LogEntry.objects.log_action(
        user_id=user.pk,
        content_type_id=get_content_type_for_model(model_object).pk,
        object_id=model_object.pk,
        object_repr=force_text(model_object),
        action_flag=ADDITION if is_create else CHANGE,
        change_message=message,
    )
