import getpass
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse
from django.core.management.base import BaseCommand
from pact.management.commands.constants import RETRY_LIMIT
from six.moves import input


class PactMigrateCommand(BaseCommand):
    help = "OTA restore from pact server"

    def get_credentials(self):
        self.username = input("""\tEnter pact username: """)
        if self.username == "":
            return

        self.password = getpass.getpass("""\tEnter pact password: """)
        if self.password == "":
            return

        self.pact_realm = 'DJANGO'
        self.passwdmngr = six.moves.urllib.request.HTTPPasswordMgrWithDefaultRealm()
        self.authhandler = six.moves.urllib.request.HTTPDigestAuthHandler(self.passwdmngr)
        self.opener = six.moves.urllib.request.build_opener(self.authhandler)

    def get_url(self, url, retry=0):
        six.moves.urllib.request.install_opener(self.opener)
        self.passwdmngr.add_password(self.pact_realm, url, self.username, self.password)
        self.authhandler = six.moves.urllib.request.HTTPDigestAuthHandler(self.passwdmngr)
        self.opener = six.moves.urllib.request.build_opener(self.authhandler)
        try:
            req = six.moves.urllib.request.Request(url)
            res = six.moves.urllib.request.urlopen(req)
            payload = res.read()
            return payload
        except six.moves.urllib.error.HTTPError as e:
            print("\t\t\tError: %s: %s" % (url, e))
            if retry < RETRY_LIMIT:
                print("Retry %d/%d" % (retry, RETRY_LIMIT))
                return self.get_url(url, retry=retry+1)
            return None
