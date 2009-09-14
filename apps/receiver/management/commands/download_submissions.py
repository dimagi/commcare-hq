""" This script downloads submissions
from a remote CommCareHQ server

The files appear in the current working directory

"""
import sys
import urllib2
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from receiver.management.commands import util
from receiver.management.commands.generate_submissions import get_MD5_data
from receiver.models import Submission

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('-a','--all', action='store_true', dest='download_all', \
                    default=False, help='Download all files'),
    )
    help = "Downloads submissions from a specified remote commmcarehq server."
    args = "<remote_url username password>"
    label = 'IP address of the remote server (including port), username, and password'
    
    def handle(self, *args, **options):
        if len(args) != 3:
            raise CommandError('Please specify %s.' % self.label)
        remote_url = args[0]
        username = args[1]
        password = args[2]
        print "Downloading submissions from %s" % remote_url
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
        
    submissions_file = "submissions.tar"
    url = 'http://%s/api/submissions/' % remote_url
    try:
        if latest:
            MD5_buffer = get_MD5_data(Submission)
            request = util.generate_POST_request(url, MD5_buffer)
            response = urllib2.urlopen(request)
            print "Downloaded latest submissions to %s" % submissions_file
        else:
            response = urllib2.urlopen(url)
            print "Downloaded all submissions to %s" % submissions_file
        fout = open(submissions_file, 'w+b')
        fout.write(response.read())
        fout.close()
    except urllib2.URLError, e:
        # make error conditions less scary. 
        # whatever we do, though, I dont think urllib is capable
        # of reading the error message contained in the HTTP
        # 400 request body, so this message is less than helpful.
        print "Exception raised on server."
    return
