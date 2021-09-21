from django.core.management.base import BaseCommand
from django.db.models import Q

from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models import UserHistory


class Command(BaseCommand):
    help = "Add locations removed change messages on commcare user's User History records " \
           "for https://github.com/dimagi/commcare-hq/pull/30253/commits/76996b5a129be4e95f5c5bedd0aba74c50088d15"

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            action='store_true',
            dest='save',
            default=False,
            help="actually update records else just log",
        )

    def handle(self, *args, **options):
        save = options['save']
        # since we need locations removed, filter for update logs
        records = UserHistory.objects.filter(
            Q(changes__has_key='location_id') | Q(changes__has_key='assigned_location_ids'),
            user_type='CommCareUser',
            action=UserHistory.UPDATE,
        )
        with open("add_location_change_message.csv", "w") as _file:
            for record in records.order_by('pk').iterator():
                updated = False
                if 'location_id' in record.changes and record.changes['location_id'] is None:
                    if 'location' not in record.change_messages:
                        record.change_messages.update(UserChangeMessage.primary_location_removed())
                        updated = True
                if record.changes.get('assigned_location_ids') == []:
                    if 'assigned_locations' not in record.change_messages:
                        record.change_messages.update(UserChangeMessage.assigned_locations_info([]))
                        updated = True
                if updated:
                    _file.write(
                        f"{record.pk},{record.user_id},{record.changes},{record.change_messages}\n"
                    )
                    if save:
                        record.save()
