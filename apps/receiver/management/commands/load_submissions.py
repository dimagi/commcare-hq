""" This script deletes existing data and 
loads new data into the local CommCareHQ server """

import tarfile
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from receiver.management.commands import util

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('-p','--localport', action='store', dest='localport', \
                    default='8000', help='Port of local server'),
    )
    help = "Load data into CommCareHQ.\n" + \
           "1) To start from a clean server, first run './manage.py reset_xforms'\n" + \
           "2) This script assumes a local server is running. To launch your local " + \
           "server, run './manage.py runserver'"
    args = "<submissions_tar optional:schemata_tar>"
    label = 'tar file of exported submissions, tar file of exported schemata'
    
    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Please specify %s.' % self.label)
        submissions = args[0]
        if len(args)>1: schemata = args[1]
        print "WARNING: Loading new data"
        util.are_you_sure()

        localport = options.get('localport', 8000)
        localserver = "127.0.0.1:%s" % localserver

        # make sure to load schemas before submissions
        if len(args)>1: load_schemata(localport, schemata)
        load_submissions(localport, submissions)
        
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
        if contents.find("No submissions") != -1:
            print "No new schemas"
        else:
            print "This is not a valid submissions file"
    else:
        util.extract_and_process(submissions_file, util.submit_form, localserver)
