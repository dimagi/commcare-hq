""" 

This script removes ALL submissions from the DB (not the filesystem)
Be VERY VERY careful when using this!

"""
from optparse import make_option
from django.core.management.base import BaseCommand
from receiver.models import Submission, Attachment, SubmissionHandlingOccurrence
from django_rest_interface import util as rest_util

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
            rest_util.are_you_sure()
        reset_submits()

def reset_submits():
    Submission.objects.all().delete()
    Attachment.objects.all().delete()
    SubmissionHandlingOccurrence.objects.all().delete()
