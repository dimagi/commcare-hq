from django.core.management.base import NoArgsCommand
from pillowtop.run_pillowtop import import_pillows

class Command(NoArgsCommand):
    help = "Reset checkpoints for pillowtop"
    def handle_noargs(self, **options):
        if options.get('interactive'):
            confirm = raw_input("""
            You have requested to reset the checkpoints for pillowtop. This is an irreversible
            operation, and may take a long time, and cause extraneous updates to the requisite
            consumers of the _changes feeds  Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """)
        else:
            confirm = 'yes'

        if confirm != 'yes':
            print "Reset cancelled."
            return

        for pillow in import_pillows():
            print "Resetting checkpoint for %s" % pillow.get_checkpoint_doc_name()
            pillow.reset_checkpoint()




