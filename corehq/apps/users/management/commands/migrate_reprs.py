import logging

from django.core.management.base import BaseCommand
from django.db.models import Q
from corehq.apps.users.models import UserHistory
from corehq.apps.users.util import cached_user_id_to_username

from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Adds user_repr and changed_by_repr to UserHistory log if not already present"

    def handle(self):
        records = UserHistory.objects.filter(Q(user_repr__isnull=True) | Q(changed_by_repr__isnull=True))
        for user_history in with_progress_bar(records.order_by('pk').iterator(), records.count()):
            try:
                migrate(user_history)
            except Exception as e:
                logging.error(f"{user_history.pk}: {e}")


def migrate(user_history):
    was_change = False
    if user_history.changed_by == SYSTEM_USER_ID:
        changed_by_repr = SYSTEM_USER_ID
    else:
        changed_by_repr = cached_user_id_to_username(user_history.changed_by)

    user_repr = cached_user_id_to_username(user_history.user_id)

    if user_history.changed_by_repr != changed_by_repr or user_history.user_repr != user_repr:
        was_change = True
    if changed_by_repr:
        user_history.changed_by_repr = changed_by_repr
    if user_repr:
        user_history.user_repr = user_repr
    if was_change:
        user_history.save()
