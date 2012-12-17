from StringIO import StringIO
from django.test.client import RequestFactory
from datetime import datetime
import getpass
import urllib2
from django.core.management.base import NoArgsCommand
from restkit import Resource
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

    def submit_xform_rf(self, action, submission_xml_string):
#        received_on = request.META.get('HTTP_X_SUBMIT_TIME')
#        date_header = request.META.get('HTTP_DATE')
#        if received_on:
#            doc.received_on = string_to_datetime(received_on)
#        if date_header:
#            comes in as:
#            Mon, 11 Apr 2011 18:24:43 GMT
#            goes out as:
#            2011-04-11T18:24:43Z
#            try:
#                date = datetime.strptime(date_header, "%a, %d %b %Y %H:%M:%S GMT")
#                date = datetime.strftime(date, "%Y-%m-%dT%H:%M:%SZ")

        server_date = action.get('server_date', None)
        phone_date = action.get('date', None)

        extra_meta = {}

        if phone_date:
            date = datetime.strptime(phone_date, "%Y-%m-%dT%H:%M:%SZ")
            date = datetime.strftime(date, "%a, %d %b %Y %H:%M:%S GMT")
            extra_meta['HTTP_DATE'] = date

        if server_date:
            extra_meta['HTTP_X_SUBMIT_TIME'] = server_date
        else:
            if phone_date is not None:
                extra_meta['HTTP_X_SUBMIT_TIME'] = phone_date
        submit_xform('/a/pact/receiver', PACT_DOMAIN, submission_xml_string, extra_meta=extra_meta)
