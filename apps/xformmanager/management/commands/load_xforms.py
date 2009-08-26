""" This script deletes existing data and 
loads new data into the local CommCareHQ server """

from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from xformmanager.management.commands import util
from xformmanager.management.commands.reset_xforms import reset_xforms, reset_submits

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('--localport', action='store', dest='localport', \
                    default='8000', help='Port of local server'),
    )
    help = "Load data into CommCareHQ"
    args = "<schemata_tar submissions_tar>"
    label = 'tar file of exported schemata, tar file of exported submissions'
    
    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError('Please specify %s.' % self.label)
        schemata = args[0]
        submissions = args[1]
        print "WARNING: Deleting all registered xforms and submissions, " + \
              "and loading %s and %s" % (schemata, submissions)
        util.are_you_sure()

        # clear self
        reset_xforms()
        reset_submits()
                
        localport = options.get('localport', 8000)
        load_xforms(localport, schemata, submissions)
        
    def __del__(self):
        pass

def load_xforms(localport, schemata, submissions):
    """ This script loads new data into the local CommCareHQ server
    
    Arguments: 
    args[0] - tar file of exported schemata
    args[1] - tar file of exported submissions
    """
    # import settings
    localserver = "127.0.0.1:%s" % localport
    util.extract_and_process(schemata, util.submit_schema, localserver)
    util.extract_and_process(submissions, util.submit_form, localserver)
