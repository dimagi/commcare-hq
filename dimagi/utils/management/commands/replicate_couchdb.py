import json
import urllib2
from dimagi.utils.couch.database import get_db
from django.core.management import call_command
from django.core.management.base import CommandError, BaseCommand
from optparse import make_option
import os
import settings

class Command(BaseCommand):
    help = "Replicate a set of docs to your local couch instance."
    option_list = BaseCommand.option_list + (
        #       make_option('--file', action='store', dest='file', default=None, help='File to upload REQUIRED', type='string'),
        #       make_option('--url', action='store', dest='url', default=None, help='URL to upload to*', type='string'),
        make_option('--username', action='store', dest='username', default=None,
            help='Username for remote couchdb instance.'),
        make_option('--password', action='store', dest='password', default=None,
            help='Password for remote couchdb instance.'),
        )
    args = '<url> [--username <username> --password <password>]'#"[--file <filename> --url <url> [optional --method {curl | python} --chunked --odk]]"
    label = "Replicate couch"

    def handle(self, *args, **options):
        url = args[0]

        username = options.get('username', None)
        password = options.get('password', None)

        if username and password:
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, url, username, password)
            auth_handler = urllib2.HTTPBasicAuthHandler(passman)
            opener = urllib2.build_opener(auth_handler)
            urllib2.install_opener(opener)

        db = get_db()

        urlobj = urllib2.urlopen(url)
        data = urlobj.read()
        json_data = json.loads(data)
        print "Got %d rows" % json_data['total_rows']
        successes = 0
        failures = 0
        for r in json_data['rows']:
            try:
                print db.save_doc(r)
                successes += 1
            except:
                failures += 1
        if successes:
            print "Successfully saved %d docs." % successes
        if failures:
            print "Failed to save %d docs." % failures

