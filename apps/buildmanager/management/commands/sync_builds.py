""" This script downloads synchronization data from a remote server,
deletes local xforms and submissions, and loads the data

"""
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from django_rest_interface import util as rest_util
from receiver.management.commands.generate_submissions import generate_submissions
from receiver.management.commands.load_submissions import load_submissions

class Command(LabelCommand):
    help = "Synchronizes CommCareHQ builds with a specified remote server."
    args = "<remote_ip username password local_dns>"
    label = 'IP address of the remote server (including port), ' + \
            'username, password, and DNS of local server'
    
    def handle(self, *args, **options):
        if len(args) < 3:
            raise CommandError('Please specify %s.' % self.label)
        remote_ip = args[0]
        username = args[1]
        password = args[2]
        local_dns = "127.0.0.1:8000"
        if len(args) == 4:
            local_dns = args[3]
        print "This script assumes a local server is running. " + \
              "To launch your local server, run './manage.py runserver'"
        rest_util.are_you_sure()
        synchronize_builds(remote_ip, username, password, local_dns)
                
    def __del__(self):
        pass
    
def synchronize_builds(remote_ip, username, password, local_server):
    file = 'builds.tar'
    # TODO
    pass
