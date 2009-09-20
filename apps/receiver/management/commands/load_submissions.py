""" This script deletes existing data and 
loads new data into the local CommCareHQ server """

import tarfile
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from receiver.management.commands.util import submit_form
from django_rest_interface import util as rest_util

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('-p','--localport', action='store', dest='localport', \
                    default='8000', help='Port of local server'),
    )
    help = "Load data into CommCareHQ.\n" + \
           "1) To start from a clean server, first run './manage.py reset_xforms'\n" + \
           "2) This script assumes a local server is running. To launch your local " + \
           "server, run './manage.py runserver'"
    args = "<submissions_tar>"
    label = 'tar file of exported submissions, tar file of exported schemata'
    
    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Please specify %s.' % self.label)
        submissions = args[0]
        print "WARNING: Loading new data"
        rest_util.are_you_sure()

        localport = options.get('localport', 8000)
        localserver = "127.0.0.1:%s" % localport

        # make sure to load schemas before submissions
        load_submissions(localserver, submissions)
        
    def __del__(self):
        pass

def load_submissions(localserver, submissions_file):
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
