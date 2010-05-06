"""
This script downloads synchronization data from a remote server,
deletes local xforms and submissions, and loads the data
"""
import bz2
import sys
import tarfile
import urllib2
import httplib
import cStringIO
from urlparse import urlparse
from optparse import make_option
from django.core.management.base import LabelCommand, CommandError
from django_rest_interface import util as rest_util
from xformmanager.management.commands.util import submit_schema
from xformmanager.models import FormDefModel

class Command(LabelCommand):
    option_list = LabelCommand.option_list + (
        make_option('-q','--quiet', action='store_false', dest='verbose', \
                    default=True, help='Quiet output'),
        make_option('-?','--debug', action='store_true', dest='debug', \
                    default=False, help='Generate some files'),
    )
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
        verbose = options.get('verbose', True)
        debug = options.get('debug', False)
        if verbose:
            print "This script assumes a local server is running. " + \
                  "To launch your local server, run './manage.py runserver'"
            rest_util.are_you_sure()
        
        file = "schemata.tar"
        generate_schemata(remote_ip, username, \
                          password, download=True, to=file, debug=False)
        if local_dns:
            load_schemata(file, local_dns)
        else:
            load_schemata(file)
        
    def __del__(self):
        pass

def generate_schemata(remote_url, username, password, latest=True, download=False, to="schemata.tar", debug=False):
    """ Generate sync data from remote server
    
    remote_url: url of remote server (ip:port)
    username, password: credentials for logging in
    """
    status = rest_util.login(remote_url, username, password)
    if not status:
        print "Sorry. Your credentials were not accepted."
        sys.exit()    
    url = 'http://%s/api/xforms/?format=sync' % remote_url
    if latest:
        xmlns_buffer = rest_util.get_field_as_bz2(FormDefModel, 'target_namespace', debug)
        print "Generating latest remote schemata..."
    else:
        xmlns_buffer = ''
        print "Generating all remote submissions archive..."
    response = rest_util.request(url, username, password, xmlns_buffer)
    print "Generated"

    if download:
        fout = open(to, 'w+b')
        fout.write(response.read())
        fout.close()
        print "Schemata downloaded to %s" % to
    return response 

def load_schemata(schemata_file, localserver="127.0.0.1:8000"):
    """ This script loads new data into the local CommCareHQ server
    
    Arguments: 
    args[0] - tar file of exported schemata
    """
    if not tarfile.is_tarfile(schemata_file):
        fin = open(schemata_file)
        contents = fin.read(256)
        fin.close()
        if contents.lower().find("no ") != -1:
            print "No new schemata"
        else:
            print "This is not a valid schemata file"
    else:
        rest_util.extract_and_process(schemata_file, submit_schema, localserver)
