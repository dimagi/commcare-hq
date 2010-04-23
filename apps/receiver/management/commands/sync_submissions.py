""" This script downloads synchronization data from a remote server,
deletes local xforms and submissions, and loads the data

"""
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from django_rest_interface import util as rest_util
from receiver.management.commands.generate_submissions import generate_submissions
from receiver.management.commands.load_submissions import load_submissions

class Command(LabelCommand):
    help = "Synchronizes CommCareHQ with a specified remote server."
    args = "<remote_ip username password local_dns>"
    label = 'IP address of the remote server (including port), ' + \
            'username, password, and DNS of local server'
    
    def handle(self, *args, **options):
        if len(args) < 3:
            raise CommandError('Please specify %s.' % self.label)
        remote_ip = args[0]
        username = args[1]
        password = args[2]
        local_dns = None
        if len(args) == 4:
            local_dns = args[3]
        print "This script assumes a local server is running. " + \
              "To launch your local server, run './manage.py runserver'"
        rest_util.are_you_sure()
        
        if local_dns:
            synchronize_submissions(remote_ip, username, password, local_dns)
        else:
            synchronize_submissions(remote_ip, username, password)
                
    def __del__(self):
        pass
    
def synchronize_submissions(remote_ip, username, password, local_server="127.0.0.1:8000"):
    file = 'submissions.tar'
    generate_submissions(remote_ip, username, password, \
                         download=True, to=file)
    load_submissions(file, local_server)
