""" This script generates all the necessary data to 
synchronize with a remote CommCareHQ server on that server.
This is only really useful if you intend to manually
scp/rsync data to your local server, which requires a
login to the remote server. So this is not the standard
synchronization workflow (but is necessary for low-connectivity
settings)

"""
import bz2
import sys
import urllib2
import httplib
import cStringIO
from urlparse import urlparse
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from django_rest_interface import util as rest_util
from receiver.models import Submission

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('-a','--all', action='store_true', dest='all', \
                    default=False, help='Generate all files'),
        make_option('-?','--debug', action='store_true', dest='debug', \
                    default=False, help='Generate some files'),
        make_option('-d','--download', action='store_true', dest='download', \
                    default=False, help='Download files.'),
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
        all = options.get('all', False)
        debug = options.get('debug', False)
        download = options.get('download', False)
        generate_submissions(remote_url, username, password, not all, debug, download)
        
    def __del__(self):
        pass

def generate_submissions(remote_url, username, password, latest=True, debug=False, download=False, to='submissions.tar'):
    """ Generate sync data from remote server
    
    remote_url: url of remote server (ip:port)
    username, password: credentials for logging in
    """
    status = rest_util.login(remote_url, username, password)
    if not status:
        print "Sorry. Your credentials were not accepted."
        sys.exit()
    
    url = 'http://%s/api/submissions/' % remote_url
    if latest:
        MD5_buffer = rest_util.get_field_as_bz2(Submission, 'checksum', debug)
        response = rest_util.request(url, username, password, MD5_buffer)
        print "Generated latest remote submissions"
    else:
        response = urllib2.urlopen(url)
        print "Generated all remote submissions archive"
    if download:
        fout = open(to, 'w+b')
        fout.write(response.read())
        fout.close()
        print "Submissions downloaded to %s" % to
    else:
        # Check for status messages
        # (i think tar payloads always begin 'BZ'...)
        response = response.read(255)
        if response[:2] != "BZ":
            print response
    return response
