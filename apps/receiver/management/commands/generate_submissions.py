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
from receiver.management.commands import util
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

def generate_submissions(remote_url, username, password, latest=True, debug=False, download=False):
    """ Generate sync data from remote server
    
    remote_url: url of remote server (ip:port)
    username, password: credentials for logging in
    """
    status = util.login(remote_url, username, password)
    if not status:
        print "Sorry. Your credentials were not accepted."
        sys.exit()
    
    url = 'http://%s/api/submissions/' % remote_url
    if latest:
        MD5_buffer = get_MD5_data(Submission, debug)

        up = urlparse(url)
        conn = httplib.HTTPConnection(up.netloc)
        conn.request('POST', up.path, MD5_buffer, {'Content-Type': 'application/bz2', 'User-Agent': 'CCHQ-submitfromfile-python-v0.1'})
        response = conn.getresponse()
        
        print "Generated latest remote submissions"
    else:
        response = urllib2.urlopen(url)
        print "Generated all remote submissions archive"
    if download:
        submissions_file = "submissions.tar"
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
        print "Submissions downloaded to %s" % submissions_file        
    return response

def get_MD5_data(django_model, debug=False):
    """ generate a string with all MD5s.
    Some operations require a buffer...
    
    django_model - django model with a 'checksum' property
                   which we will POST in a tarfile
    """
    string = cStringIO.StringIO()
    if not debug:
        objs = django_model.objects.all().order_by('checksum')
    else:
        print "DEBUG MODE: Only generating some submissions"
        # arbitrarily return only 10 of the MD5s
        objs = django_model.objects.all().order_by('checksum')[:5]
    for obj in objs:
        string.write(unicode(obj.checksum) + '\n')
    return bz2.compress(string.getvalue())

def get_MD5_handle(django_model):
    """ ...some operations require a handle 
    
    returns a READ-ONLY handle
    """
    buffer = get_MD5_data(django_model)
    string = cStringIO.StringIO(buffer)
    return string

