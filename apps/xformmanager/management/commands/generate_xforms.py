""" This script generates all the necessary data to 
synchronize with a remote CommCareHQ server on that server.
This is only really useful if you intend to manually
scp/rsync data to your local server, which requires a
login to the remote server. So this is not the standard
synchronization workflow (but is necessary for low-connectivity
settings)

"""
import sys
import urllib
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from xformmanager.management.commands import util
from xformmanager.models import FormDefModel
from receiver.models import Submission

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('-a','--all', action='store_true', dest='download_all', \
                    default=False, help='Download all files'),
    )
    help = "Generate synchronization files on a CommCareHQ remote server."
    args = "<remote_url username password>"
    label = 'IP address of the remote server (including port), username, and password'
    
    def handle(self, *args, **options):
        if len(args) != 3:
            raise CommandError('Please specify %s.' % self.label)
        remote_url = args[0]
        username = args[1]
        password = args[2]
        print "Generating synchronization data from %s" % remote_url
        download_all = options.get('download_all', False)
        generate_xforms(remote_url, username, password, not download_all)
        
    def __del__(self):
        pass

def generate_xforms(remote_url, username, password, latest=True):
    """ Generate sync data from remote server
    
    remote_url: url of remote server (ip:port)
    username, password: credentials for logging in
    """
    status = util.login(remote_url, username, password)
    if not status:
        print "Sorry. Your credentials were not accepted."
        sys.exit()
        
    def _generate_latest(url, django_model):
        # for now, we assume schemas and submissions appear with monotonically 
        # increasing id's. I doubt this is always the case.
        # TODO: fix 
        start_id = -1
        received_count = django_model.objects.count()
        if url.find("?") == -1: url = url + "?"
        else: url = url + "&"
        url = url + ("received_count=%s" % received_count)
        print "Hitting %s" % url
        # TODO - update this to use content-disposition instead of FILE_NAME
        urllib.urlopen(url)
        print "Generated tar from %s" % url
    
    url = 'http://%s/api/xforms/?format=sync' % remote_url
    if latest: _generate_latest(url, FormDefModel)
    else: 
        urllib.urlopen(url)
        print "Generated remote schemata archive"
    
    # TODO - move this to receiver/management?
    url = 'http://%s/api/submissions/' % remote_url
    if latest: _generate_latest(url, Submission)
    else: 
        urllib.urlopen(url)
        print "Generated remote submissions archive"
    return
