from optparse import make_option
from django.core.management.base import LabelCommand
import sys
from pillowtop import get_pillow_by_name, get_all_pillow_classes


class Command(LabelCommand):
    help = "Reset checkpoints for pillowtop"
    args = '<pillow_class>'
    label = 'Pillow class'

    option_list = LabelCommand.option_list + \
                  (
                     make_option('--noinput',
                                  action='store_true',
                                  dest='interactive',
                                  default=False,
                                  help="Suppress confirmation messages - dangerous mode!"),
                  )

    def handle(self, *labels, **options):
        """
        More targeted pillow checkpoint reset system - must specify the pillow class_name to reset the checkpoint
        """

        if not labels:
            pillow_class_names = [cls.__name__
                                  for cls in get_all_pillow_classes()]
            print "\nNo pillow class specified, options are:\n\t%s\n" % ('\n\t'.join(pillow_class_names))
            sys.exit()

        pillow_class_name = labels[0]
        pillow_to_use = get_pillow_by_name(pillow_class_name)
        if not pillow_to_use:
            print ""
            print "\n\tPillow class [%s] not in configuration, what are you trying to do?\n" % pillow_class_name
            sys.exit()

        if not options.get('interactive'):
            confirm = raw_input("""
            You have requested to reset the checkpoints for the pillow [%s]. This is an irreversible
            operation, and may take a long time, and cause extraneous updates to the requisite
            consumers of the _changes feeds  Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """  % pillow_class_name)
        else:
            confirm = 'yes'

        if confirm != 'yes':
            print "Reset cancelled."
            return

        print "Resetting checkpoint for %s" % pillow_to_use.checkpoint.checkpoint_id
        print "\tOld checkpoint: %s" % pillow_to_use.get_checkpoint()['seq']
        pillow_to_use.checkpoint.reset()
        print "\n\tNew checkpoint reset to zero"
