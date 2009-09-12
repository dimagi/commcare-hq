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
import cStringIO
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from receiver.management.commands import util
from receiver.management.commands.forms import POST_file
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
        generate_submissions(remote_url, username, password, not download_all)
        
    def __del__(self):
        pass

def generate_submissions(remote_url, username, password, latest=True):
    """ Generate sync data from remote server
    
    remote_url: url of remote server (ip:port)
    username, password: credentials for logging in
    """
    status = util.login(remote_url, username, password)
    if not status:
        print "Sorry. Your credentials were not accepted."
        sys.exit()
    
    url = 'http://%s/api/submissions/' % remote_url
    try:
        if latest:
            POST_MD5(url, Submission)
            print "Generated latest remote submissions archive"
        else:
            urllib2.urlopen(url)
            print "Generated remote submissions archive"
    except urllib2.URLError, e:
        # make error conditions less scary. 
        # whatever we do, though, I dont think urllib2 is capable
        # of reading the error message contained in the HTTP
        # 400 request body, so this message is less than helpful.
        print "Exception raised on server."
    return


def POST_MD5(url, django_model):
    """ generate a string with all MD5s
    
    url - URL of remote server
    django_model - django model with a 'checksum' property
                   which we will POST in a tarfile
    """
    string = cStringIO.StringIO()
    objs = django_model.objects.all().order_by('checksum')
    for obj in objs:
        string.write(unicode(obj.checksum) + '\n')
    md5_compressed = bz2.compress(string.getvalue())
    
    # POST that string to destination URL
    POST_file(md5_compressed, url)
