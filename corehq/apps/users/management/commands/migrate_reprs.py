import logging

from django.core.management.base import BaseCommand
from corehq.apps.users.models import UserHistory
from corehq.apps.users.util import user_id_to_username

from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Adds user_repr and changed_by_repr to UserHistory log if not already present"

    def handle(self):
        records = UserHistory.objects
        for user_history in with_progress_bar(records.order_by('pk').iterator(), 185):
            if user_history.changed_by_repr is None or user_history.user_repr is None:
                try:
                    migrate(user_history)
                except Exception as e:
                    logging.error(f"{user_history.pk}: {e}")


def migrate(user_history):
    if user_history.changed_by == SYSTEM_USER_ID:
        changed_by_repr = SYSTEM_USER_ID
    else:
        changed_by_repr = user_id_to_username(user_history.changed_by)

    user_repr = user_id_to_username(user_history.user_id)

    if changed_by_repr:
        user_history.change_by_repr = changed_by_repr
    if user_repr:
        user_history.user_repr = user_repr
    if changed_by_repr or user_repr:
        user_history.save()
