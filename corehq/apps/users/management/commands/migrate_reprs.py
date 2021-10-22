import logging

from django.core.management.base import BaseCommand
from corehq.apps.users.models import UserHistory
from corehq.apps.users.util import user_id_to_username

from corehq.apps.users.util import SYSTEM_USER_ID


class Command(BaseCommand):
    help = "Adds user_repr and changed_by_repr to UserHistory log if not already present"

    def handle(self):
        records = UserHistory.objects
        for user_history in records.order_by('pk').iterator():
            try:
                migrate(user_history)
            except Exception as e:
                logging.error(f"{user_history.pk}: {e}")


def migrate(user_history):
    if user_history.changed_by == SYSTEM_USER_ID:
        change_by_repr = SYSTEM_USER_ID
    else:
        change_by_repr = user_id_to_username(user_history.changed_by)

    user_repr = user_id_to_username(user_history.user_id)

    if change_by_repr:
        user_history.change_by_repr = change_by_repr
    if user_repr:
        user_history.user_repr = user_repr
    if change_by_repr or user_repr:
        user_history.save()
