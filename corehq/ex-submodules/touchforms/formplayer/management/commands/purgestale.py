from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
from datetime import datetime, timedelta
import urllib2
import json

class Command(BaseCommand):
    args = '<stale threshold age>'
    help = 'enter age as suitable for timedelta(), e.g., minutes=30'
    option_list = BaseCommand.option_list + (
        make_option('-s', dest='server_url', help='url of formplayer server', default='127.0.0.1:4444/'),
    )

    def handle(self, *args, **options):
        try:
            timespec = args[0]
        except IndexError:
            raise ValueError('time spec required')

        server = options['server_url']
        if not server.startswith('http://') and not server.startswith('https://'):
            server = 'http://' + server

        window = eval('timedelta(%s)' % timespec)
        payload = {'action': 'purge-stale', 'window': sdelt(window)}

        print 'purging sessions on %s older than %ds' % (server, payload['window'])

        resp = urllib2.urlopen(server, json.dumps(payload))
        print resp.read()
        
def sdelt(delta):
    return 86400. * delta.days + delta.seconds + 1.0e-6 * delta.microseconds
