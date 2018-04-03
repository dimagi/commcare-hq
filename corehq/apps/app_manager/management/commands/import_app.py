from __future__ import absolute_import
from __future__ import unicode_literals
from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
import requests
from requests.auth import HTTPDigestAuth
from corehq.apps.app_manager.models import import_app


class Command(BaseCommand):
    help = ("Import an app from another Commcare instance")

    def add_arguments(self, parser):
        parser.add_argument(
            'domain'
        )
        parser.add_argument(
            'app_id',
        )
        parser.add_argument(
            '-u',
            '--username',
            action='store',
            dest='username',
            help='Username',
        )
        parser.add_argument(
            '-p',
            '--password',
            action='store',
            dest='password',
            help='Password',
        )
        parser.add_argument(
            '-d',
            '--to_domain',
            action='store',
            dest='to_domain',
            help='The domain to import the app into.',
        )
        parser.add_argument(
            '-n',
            '--to_name',
            action='store',
            dest='to_name',
            default=None,
            help='The name to give to the imported app',
        )
        parser.add_argument(
            '--url',
            action='store',
            dest='url',
            default='https://www.commcarehq.org',
            help='The URL of the CommCare instance.',
        )

    def _get_required_option(self, name, options):
        value = options.get(name)
        if not value:
            raise CommandError("Option: '--{}' must be specified".format(name))
        return value

    def handle(self, domain, app_id, **options):
        username = self._get_required_option('username', options)
        target_domain = self._get_required_option('to_domain', options)

        name = options['to_name']
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
        if not name:
            name = app_source['name']
        app = import_app(app_source, target_domain, {'name': name})
        return "Created app '{}' at /a/{}/apps/view/{}/".format(app.name, app.domain, app.id)
