from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand

from pillowtop.models import DjangoPillowCheckpoint


class Command(BaseCommand):
    """
    One off command to migrate pillow checkpoints after ES upgrade.
    """
    help = "Migrate the esupgrade checkpoints"

    option_list = BaseCommand.option_list + (
        make_option(
            '--check',
            action='store_true',
            dest='check',
            default=False,
            help="Just print the changes",
        ),
        make_option(
            '--undo',
            action='store_true',
            dest='undo',
            default=False,
            help="Undo the changes",
        ),
    )

    def handle(self, *args, **options):
        check = options['check']
        undo = options['undo']

        upgrade_checkpoints = DjangoPillowCheckpoint.objects.filter(checkpoint_id__endswith='esupgrade')
        for upgrade_cp in upgrade_checkpoints:
            prefix, _ = upgrade_cp.checkpoint_id.rsplit('.', 1)
            current_cp_id = '{}.{}'.format(prefix, settings.PILLOWTOP_MACHINE_ID)
            try:
                current_cp = DjangoPillowCheckpoint.objects.get(checkpoint_id=current_cp_id)
            except DjangoPillowCheckpoint.DoesNotExist:
                print('Matching checkpoint not found: {}'.format(upgrade_cp.checkpoint_id))
            else:
                if undo:
                    self.undo(current_cp, check)
                else:
                    self.migrate(upgrade_cp, current_cp, check)

    @staticmethod
    def migrate(upgrade_cp, current_cp, check):
        print('Copying sequence from: {} -> {}'.format(
            upgrade_cp.checkpoint_id, current_cp.checkpoint_id
        ))
        if check:
            print('Old seq: {}'.format(current_cp.sequence))
            print('New seq: {}'.format(upgrade_cp.sequence))
        else:
            current_cp.old_sequence = current_cp.sequence
            current_cp.sequence = upgrade_cp.sequence
            current_cp.save()

    @staticmethod
    def undo(current_cp, check):
        if not current_cp.old_sequence:
            print('Unable to revert empty to old sequence: {}'.format(current_cp.checkpoint_id))
            return

        print('Reverting to old sequence for: {}'.format(current_cp.checkpoint_id))
        if check:
            print('Old seq: {}'.format(current_cp.sequence))
            print('New seq: {}'.format(current_cp.old_sequence))
        else:
            current_cp.sequence = current_cp.old_sequence
            current_cp.old_sequence = None
            current_cp.save()
