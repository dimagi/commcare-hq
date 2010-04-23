""" This script removes all schemas found in XSD_REPOSITORY_PATH
and associated tables. It also deletes the contents of XFORM_SUBMISSION_PATH.

"""
from optparse import make_option
from django.core.management.base import BaseCommand
from django_rest_interface import util as rest_util
from xformmanager.management.commands import util
from receiver.models import Submission, Attachment, SubmissionHandlingOccurrence

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('-q','--quiet', action='store_false', dest='verbose', \
                    default=True, help='Quiet output'),
    )
    def handle(self, *app_labels, **options):
        print "WARNING: Deleting ALL XML FILES, SUBMISSIONS, AND SCHEMA from the local server!"
        # print "WARNING: Deleting all saved xforms, schemas, and instance data."
        verbose = options.get('verbose', True)
        if verbose:
            rest_util.are_you_sure()
        reset_schema()
        
# we make these functions global so they can be reused by other scripts
def reset_schema():
    from xformmanager.storageutility import StorageUtility
    su = StorageUtility()
    su.clear(remove_submissions=True)
