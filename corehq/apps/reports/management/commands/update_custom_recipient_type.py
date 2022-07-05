from django.core.management import BaseCommand
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseTimedScheduleInstance,
    TimedScheduleInstance,
    CaseAlertScheduleInstance,
    AlertScheduleInstance,
)
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.apps.data_interfaces.models import CreateScheduleInstanceActionDefinition


class Command(BaseCommand):
    help = 'Updates a custom recipient value'

    def add_arguments(self, parser):
        parser.add_argument(
            '--current-type',
            help='The current custom type which is to be updated.',
        )
        parser.add_argument(
            '--new-type',
            help='The new custom type which the current type is to be updated to.',
        )

    def handle(self, **options):
        current_type = options.get('current_type')
        new_type = options.get('new_type')

        if not current_type or not new_type:
            raise Exception('current-type or new-type value missing')

        for db in get_db_aliases_for_partitioned_query():
            CaseTimedScheduleInstance.objects.using(db).filter(recipient_id=current_type).update(
                recipient_id=new_type
            )
            TimedScheduleInstance.objects.using(db).filter(recipient_id=current_type).update(
                recipient_id=new_type
            )
            CaseAlertScheduleInstance.objects.using(db).filter(recipient_id=current_type).update(
                recipient_id=new_type
            )
            AlertScheduleInstance.objects.using(db).filter(recipient_id=current_type).update(
                recipient_id=new_type
            )

        # Filter those not equal to [] just to be safe
        definitions = CreateScheduleInstanceActionDefinition.objects.exclude(recipients=[])

        for definition in definitions:
            recipients = definition.recipients

            has_changed = False
            for recipient in recipients:
                if recipient[0] == "CustomRecipient" and recipient[1] == current_type:
                    recipient[1] = new_type
                    has_changed = True

            if has_changed:
                definition.save()
