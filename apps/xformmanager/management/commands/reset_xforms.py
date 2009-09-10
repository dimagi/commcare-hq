""" This script removes all schemas found in XSD_REPOSITORY_PATH
and associated tables. It also deletes the contents of XFORM_SUBMISSION_PATH.

"""
from optparse import make_option
from django.core.management.base import BaseCommand
from xformmanager.management.commands import util
from receiver.models import Submission, Attachment, SubmissionHandlingOccurrence

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('-q','--quiet', action='store_false', dest='verbose', \
                    default=True, help='Quiet output'),
    )
    def handle(self, *app_labels, **options):
        print "WARNING: Deleting ALL SUBMISSIONS from the local server!"
        # print "WARNING: Deleting all saved xforms, schemas, and instance data."
        verbose = options.get('verbose', True)
        if verbose:
            util.are_you_sure()
        reset_xforms()
        # TODO - make a reset_submits command in receiver/management
        reset_submits()
        
# we make these functions global so they can be reused by other scripts
def reset_xforms():
    from xformmanager.storageutility import StorageUtility
    su = StorageUtility()
    su.clear()

# TODO - put this in receiver/management
def reset_submits():
    Submission.objects.all().delete()
    Attachment.objects.all().delete()
    SubmissionHandlingOccurrence.objects.all().delete()
