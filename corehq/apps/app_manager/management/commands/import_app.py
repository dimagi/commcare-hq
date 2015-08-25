from getpass import getpass
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.core.urlresolvers import reverse
import requests
from requests.auth import HTTPDigestAuth
from corehq.apps.app_manager.models import import_app


class Command(BaseCommand):
    args = 'source_domain app_id'
    help = ("Import an app from another Commcare instance")
    option_list = BaseCommand.option_list + (
        make_option('-u', '--username',
                    action='store',
                    dest='username',
                    help='Username'),
        make_option('-p', '--password',
                    action='store',
                    dest='password',
                    help='Password'),
        make_option('-d', '--to_domain',
                    action='store',
                    dest='to_domain',
                    help='The domain to import the app into.'),
        make_option('-n', '--to_name',
                    action='store',
                    dest='to_name',
                    default='',
                    help='The name to give to the imported app'),
        make_option('--url',
                    action='store',
                    dest='url',
                    default='https://www.commcarehq.org',
                    help='The URL of the CommCare instance.'),
    )

    def _get_required_option(self, name, **options):
        value = options.get(name)
        if not value:
            raise CommandError("Option: '--{}' must be specified".format(name))
        return value

    def handle(self, *args, **options):
        domain, app_id = args

        username = self._get_required_option('username')
        target_domain = self._get_required_option('to_domain')
        name = self._get_required_option('to_name')

        url_base = options['url']
        password = options['password']
        if not password:
            password = getpass("Please enter the password for '{}': ".format(username))

        url = reverse('app_source', kwargs={'domain': domain, 'app_id': app_id})
        full_url = '{}{}'.format(url_base, url)
        resp = requests.get(full_url, auth=HTTPDigestAuth(username, password))
        if not resp.status_code == 200:
            return "Command Failed: {}: {}".format(resp.status_code, resp.text)

        app_source = resp.json()
        import_app(app_source, target_domain, {'name': name})
