from StringIO import StringIO
import getpass
import urllib2
from django.core.management.base import NoArgsCommand
from django.test.client import RequestFactory
from restkit import Resource
from pact.management.commands.constants import RETRY_LIMIT, PACT_DOMAIN
from corehq.apps.receiverwrapper import views as rcv_views


class PactMigrateCommand(NoArgsCommand):
    help = "OTA restore from pact server"
    option_list = NoArgsCommand.option_list + (
    )


    def get_credentials(self):
        self.username = raw_input("""\tEnter pact username: """)
        if self.username == "":
            return

        self.password = getpass.getpass("""\tEnter pact password: """)
        if self.password == "":
            return

        self.pact_realm = 'DJANGO'
        self.passwdmngr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.authhandler = urllib2.HTTPDigestAuthHandler(self.passwdmngr)
        self.opener = urllib2.build_opener(self.authhandler)



    def get_url(self, url, retry=0):
        urllib2.install_opener(self.opener)
        self.passwdmngr.add_password(self.pact_realm, url, self.username, self.password)
        self.authhandler = urllib2.HTTPDigestAuthHandler(self.passwdmngr)
        self.opener = urllib2.build_opener(self.authhandler)
        try:
            req = urllib2.Request(url)
            res = urllib2.urlopen(req)
            payload = res.read()
            return payload
        except urllib2.HTTPError, e:
            print "\t\t\tError: %s: %s" % (url, e)
            if retry < RETRY_LIMIT:
                print "Retry %d/%d" % (retry,RETRY_LIMIT)
                return self.get_url(url, retry=retry+1)

    def submit_xform(self, submission_xml_string):
        p = Resource('http://localhost:8000')
        f = StringIO(submission_xml_string.encode('utf-8'))
        f.name = 'form.xml'
        res = p.post('/a/pact/receiver', payload= { 'xml_submission_file': f }, headers={'content-type':"multipart/form-data"})
        return res

    def submit_xform_rf(self, submission_xml_string):
        rf = RequestFactory()
        f = StringIO(submission_xml_string.encode('utf-8'))
        f.name = 'form.xml'
        req = rf.post('/a/pact/receiver', data = { 'xml_submission_file': f }) #, content_type='multipart/form-data')
        return rcv_views.post(req, PACT_DOMAIN)

