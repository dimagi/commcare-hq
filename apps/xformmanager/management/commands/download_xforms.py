""" This script downloads all the necessary data to 
synchronize with a remote CommCareHQ server

The files appear in the current working directory

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
    help = "Synchronizes CommCareHQ with a specified remote server."
    args = "<remote_url username password>"
    label = 'IP address of the remote server (including port), username, and password'
    
    def handle(self, *args, **options):
        if len(args) != 3:
            raise CommandError('Please specify %s.' % self.label)
        remote_url = args[0]
        username = args[1]
        password = args[2]
        print "Downloading synchronization data from %s" % remote_url
        download_all = options.get('download_all', False)
        download_xforms(remote_url, username, password, not download_all)
        
    def __del__(self):
        pass

def download_xforms(remote_url, username, password, latest=True):
    """ Download sync data from remote server
    
    remote_url: url of remote server (ip:port)
    username, password: credentials for logging in
    """
    status = util.login(remote_url, username, password)
    if not status:
        print "Sorry. Your credentials were not accepted."
        sys.exit()
        
    def _download_latest(url, django_model, to_file):
        # for now, we assume schemas and submissions appear with monotonically 
        # increasing id's. I doubt this is always the case.
        # TODO: fix 
        try: start_id = django_model.objects.order_by('-id')[0].pk + 1
        except IndexError: pass
        if start_id:
            if url.find("?") == -1:
                # no existing GET variables
                url = url + ("?start-id=%s" % start_id)
            else:
                # add new GET variable
                url = url + ("&start-id=%s" % start_id)
        # TODO - update this to use content-disposition instead of FILE_NAME
        urllib.urlretrieve(url, to_file)
        print "Downloaded %s" % to_file
    
    schemata_file = "schemata.tar"
    url = 'http://%s/api/xforms/?format=sync' % remote_url
    if latest: _download_latest(url, FormDefModel, schemata_file)
    else: 
        urllib.urlretrieve(url, schemata_file)
        print "Downloaded all schemas to %s" % schemata_file
    
    # TODO - move this to receiver/management?
    submissions_file = "submissions.tar"
    url = 'http://%s/api/submissions/' % remote_url
    if latest: _download_latest(url, Submission, submissions_file)
    else: 
        urllib.urlretrieve(url, submissions_file)
        print "Downloaded all submissions to %s" % submissions_file
    return (schemata_file, submissions_file)
