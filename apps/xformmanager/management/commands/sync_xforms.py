""" This script downloads synchronization data from a remote server,
deletes local xforms and submissions, and loads the data

"""
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from xformmanager.management.commands.download_xforms import download_xforms
from xformmanager.management.commands.load_xforms import load_schemata, load_submissions
from xformmanager.management.commands.reset_xforms import reset_xforms, reset_submits
import tarfile

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('--localport', action='store', dest='localport', \
                    default='8000', help='Port of local server'),
    )
    help = "Synchronizes CommCareHQ with a specified remote server."
    args = "<remote_ip username password>"
    label = 'IP address of the remote server (including port), ' + \
            'username, and password'
    
    def handle(self, *args, **options):
        if len(args) != 3:
            raise CommandError('Please specify %s.' % self.label)
        remote_ip = args[0]
        username = args[1]
        password = args[2]
        print "WARNING: This command will DELETE all existing xforms " +\
              "and synchronize with the remote server at %s " % remote_ip
        #util.are_you_sure()

        (schemata, submissions) = download_xforms(remote_ip, username, password)
        
        # (when downloading from self, the following is useful to prevent
        # file concurrent access errors)
        # import time
        # time.sleep(5)
        
        localport = options.get('localport', 8000)
        load_schemata(localport, schemata)
        load_submissions(localport, submissions)
        
    def __del__(self):
        pass

