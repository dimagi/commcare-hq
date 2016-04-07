from StringIO import StringIO
from django.test.client import RequestFactory
from datetime import datetime
import getpass
import urllib2
from django.core.management.base import NoArgsCommand
from restkit import Resource
from corehq.util.dates import iso_string_to_datetime
from pact.management.commands.constants import RETRY_LIMIT
from pact.enums import PACT_DOMAIN
from pact.utils import submit_xform


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
            return None
