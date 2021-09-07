import json
import logging

from openpyxl import Workbook

from django.contrib.admin.models import LogEntry
from django.contrib.admin.options import get_content_type_for_model
from django.core.management.base import BaseCommand
from django.utils.encoding import force_text

from corehq.apps.users.models import UserHistory


class Command(BaseCommand):
    help = "Migrate User History records to new structure"

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            action='store_true',
            dest='save',
            default=False,
            help="actually save records else just log",
        )

    def handle(self, **options):
        save = options['save']
        wb = Workbook()
        ws = wb.active
        ws.append([
            'ID', 'Message', 'Change Messages', 'Details Changes', 'Changes', 'Changes equal?',
            'Details Changed Via', 'Changed Via']
        )

        records = UserHistory.objects

        for user_history in records.all():
            try:
                migrate(user_history, save=save)
            except Exception as e:
                logging.error(f"{user_history.pk}: {e}")
            else:
                ws.append(
                    [user_history.pk,
                     user_history.message,
                     json.dumps(user_history.change_messages),
                     json.dumps(user_history.details.get('changes')),
                     json.dumps(user_history.changes),
                     user_history.details.get('changes') == user_history.changes,  # should not be False
                     user_history.details.get('changed_via'),
                     user_history.changed_via
                     ]
                )
        wb.save("migrate_user_history_to_new_structure.xlsx")


def migrate(user_history, save=False):
    """
    1. Copy over changed_via and changes to new columns
    2. convert messages into new change messages format
    3. migrate over to log entry to back up old columns before they are deleted
    """
    # ToDo: remove this if later. Just added to avoid issues during dry runs
    if hasattr(user_history, 'change_messages'):
        # a double check to avoid re-runs on records
        if user_history.message and user_history.change_messages:
            raise Exception("got a migrated record")

    # simply copy over changed_via to new column
    # changed_via should always be present
    user_history.changed_via = user_history.details.get('changed_via')
    assert user_history.changed_via, f"Missing changed_via for {user_history.pk}"

    # simply copy over user changes to new changes column
    # changes might or might not be present
    if user_history.details.get('changes'):
        user_history.changes = user_history.details['changes']

    if user_history.message:
        change_messages = create_change_messages(user_history)
        assert change_messages, f"Change message not created for message {user_history.message}"
        user_history.change_messages = change_messages

    if save:
        user_history.save()

        migrated = migrate_user_history_to_log_entry(user_history)
        assert migrated, f"Could not create log entry for User History record {user_history.pk}"


def create_change_messages(user_history):
    change_messages = {}
    return change_messages


def migrate_user_history_to_log_entry(user_history):
    """
    Add a new LogEntry for the user history record if users still in the system.
    This is only intended to keep back up of the deprecated columns (message, details) which would be migrated to
    new columns (change_messages, changes & changed_via) for debugging purposes after the deprecated columns
    are removed.
    :returns: log entry if it was created
    """
    from corehq.apps.users.models import CouchUser

    couch_user = CouchUser.get_by_user_id(user_history.user_id)
    changed_by_couch_user = CouchUser.get_by_user_id(user_history.changed_by)

    # if any of the user is missing, they must be now deleted and we can't get their django user for LogEntry
    # ignore such logs
    if couch_user and changed_by_couch_user:
        django_user = couch_user.get_django_user()
        changed_by_django_user = changed_by_couch_user.get_django_user()

        # keep a reference to the user history record
        change_message = {
            'user_history_pk': user_history.pk
        }
        # copy the deprecated text message column from UserHistory
        if user_history.message:
            change_message['message'] = user_history.message

        # copy the deprecated details column
        if user_history.details:
            change_message['details'] = user_history.details

        # reference https://github.com/dimagi/commcare-hq/blob/a1aa13913fc48cd23dfc85dc11f9412d5fe808f9/corehq/util/model_log.py#L38
        log_entry = LogEntry.objects.log_action(
            user_id=changed_by_django_user.pk,
            content_type_id=get_content_type_for_model(django_user).pk,
            object_id=django_user.pk,
            object_repr=force_text(django_user),
            action_flag=user_history.action,
            change_message=json.dumps(change_message)
        )
        log_entry.action_time = user_history.changed_at
        log_entry.save()
        return log_entry
    else:
        return False
