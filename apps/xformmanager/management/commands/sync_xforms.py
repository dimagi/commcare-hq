""" This script downloads synchronization data from a remote server,
deletes local xforms and submissions, and loads the data

"""
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from xformmanager.management.commands.download_xforms import download_xforms
from xformmanager.management.commands.load_xforms import load_xforms
from xformmanager.management.commands.reset_xforms import reset_xforms, reset_submits

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

        # make sure we finish downloading the files before we proceed with delete
        # (this is only critical when downloading from self)
        import time
        time.sleep(5)

        # clear self
        reset_xforms()
        reset_submits()

        localport = options.get('localport', 8000)
        load_xforms(localport, schemata, submissions)
        
    def __del__(self):
        pass

