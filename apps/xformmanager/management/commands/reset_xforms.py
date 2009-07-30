""" This script removes all schemas found in XSD_REPOSITORY_PATH
and associated tables. It also deletes the contents of XFORM_SUBMISSION_PATH.

It is intended to be run from the command-line.
This should be in apps.xformmanager.management.commands
We'll leave it here until django supports commands properly
(right now imports fail)

"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    
    def handle(self, *app_labels, **options):
        from xformmanager.storageutility import StorageUtility
        import logging
        import sys
        #get user verification
        print "WARNING: Deleting all saved xforms, schemas, and instance data."
        should_proceed = raw_input("Are you sure you want to proceed? (yes or no) ")
        if should_proceed != "yes":
            print "Ok, exiting."
            sys.exit()
        
        console = logging.StreamHandler()
        formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        
        su = StorageUtility()
        su.clear()
        
        logging.getLogger('').removeHandler(console)
