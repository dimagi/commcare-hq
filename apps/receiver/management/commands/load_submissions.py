""" This script deletes existing data and 
loads new data into the local CommCareHQ server """

import tarfile
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from receiver.management.commands.util import submit_form
from django_rest_interface import util as rest_util

class Command(LabelCommand):
    help = "Load data into CommCareHQ.\n" + \
           "1) To start from a clean server, first run './manage.py reset_xforms'\n" + \
           "2) This script assumes a local server is running. To launch your local " + \
           "server, run './manage.py runserver'"
    args = "<submissions_tar local_dns>"
    label = 'tar file of exported submissions and dns of local server'
    
    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Please specify %s.' % self.label)
        submissions = args[0]
        local_dns = None
        if len(args) == 2:
            local_dns = args[1]
        print "WARNING: Loading new data"
        rest_util.are_you_sure()
        
        if local_dns:
            load_submissions( submissions, local_dns )
        else:
            load_submissions( submissions )
        
    def __del__(self):
        pass

def load_submissions(submissions_file, localserver="127.0.0.1:8000"):
    """ This script loads new data into the local CommCareHQ server
    
    Arguments: 
    args[0] - tar file of exported submissions
    """
    if not tarfile.is_tarfile(submissions_file):
        fin = open(submissions_file)
        contents = fin.read(256)
        fin.close()
        if contents.lower().find("no ") != -1:
            print "No new submissions"
        else:
            print "This is not a valid submissions file"
    else:
        rest_util.extract_and_process(submissions_file, submit_form, localserver)
