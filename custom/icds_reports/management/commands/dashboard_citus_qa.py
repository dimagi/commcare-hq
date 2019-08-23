from __future__ import absolute_import, print_function
from __future__ import unicode_literals

import base64
import getpass
import json
import random
import string
import sys
from collections import defaultdict
from pprint import pprint

import json_delta
import requests
from django.core.management import CommandError
from django.core.management.base import BaseCommand
from lxml.doctestcompare import LHTMLOutputChecker

from corehq.apps.app_manager.tests.util import _check_shared
from corehq.apps.users.models import WebUser
from corehq.toggles import LOAD_DASHBOARD_FROM_CITUS
from custom.icds_reports.const import DASHBOARD_DOMAIN
from dimagi.utils.web import get_url_base
from io import open
from six.moves import zip


class SessionHolder(object):
    def __init__(self, validate, base_url, domain, *usernames):
        self.base_url = base_url
        self.domain = domain
        self.validate = validate
        self.sessions = []
        self.usernames = usernames

        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def authenticate(self):
        self.sessions = [
            _get_authed_session(username, self.base_url, validate=self.validate)
            for username in self.usernames
        ]

    def get(self, url):
        status_codes = []
        content = []
        full_url = '{}/a/{}/{}'.format(self.base_url, self.domain, url)
        content_type = None
        for i, s in enumerate(self.sessions):
            resp = s.get(full_url)
            status_codes.append(resp.status_code)
            content.append(resp.text)
            content_type = resp.headers.get('content-type')

        self.stdout('\n{}\n{}'.format(full_url, status_codes))
        if not len(set(status_codes)) == 1:
            self.print_diff(url, 'status_code', status_codes)

        if content[0] != content[1]:
            if content_type == 'application/json':
                diff = json_delta.diff(json.loads(content[0]), json.loads(content[1]), verbose=False)
                pprint(diff, indent='8')
            else:
                try:
                    _check_shared(content[0], content[1], LHTMLOutputChecker(), "html")
                except AssertionError as e:
                    self.stderr(str(e))

    def print_diff(self, url, key, values):
        self.stderr('Diff: {} {}'.format(key, url))
        for username, value in zip(self.usernames, values):
            self.stderr('\t{}: {}'.format(username, value))

    def __enter__(self):
        self.authenticate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for session in self.sessions:
            session.close()


class Command(BaseCommand):
    help = (
        "Command to aid in the QA of the ICDS Dashboard migration to CitusDB.\n"
        "Takes a list of URLs and performs a GET request for each. By default only"
        "one request per unique path is made unless '--full' is specified."
    )

    def add_arguments(self, parser):
        parser.add_argument('url_list')
        parser.add_argument(
            '-u', '--user1', help='Username of first user.'
        )
        parser.add_argument(
            '-U', '--user2', help='Username of second user.'
        )
        parser.add_argument(
            '-d', '--domain', default=DASHBOARD_DOMAIN,
        )
        parser.add_argument(
            '--full', action='store_true', help='Run all URLs.'
        )
        parser.add_argument(
            '--hq-url', default=get_url_base(), help='Base URL for CommCare HQ.'
        )

    def handle(self, url_list, user1, user2, domain, **options):
        full = options['full']
        base_url = options['hq_url']

        # only do user validation if we're querying the current site
        validate = base_url == get_url_base()

        if validate:
            u1_citus = LOAD_DASHBOARD_FROM_CITUS.enabled(user1)
            u2_citus = LOAD_DASHBOARD_FROM_CITUS.enabled(user2)
            if u1_citus == u2_citus:
                raise CommandError('Both users configured to view {} dashboard'.format(
                    'Citus' if u1_citus else 'PG'
                ))

        with open(url_list, 'r') as file:
            lines = [line.strip() for line in file.readlines()]

        by_path = defaultdict(list)
        for line in lines:
            path = line
            query = None
            if '?' in line:
                path, query = line.split('?')
            by_path[path].append(query)

        session = SessionHolder(validate, base_url, domain, user1, user2)
        session.stdout = self.stdout
        session.stderr = self.stderr
        with session:
            for path, queries in by_path.items():
                queries = queries if full else [random.choice(queries)]
                for query in queries:
                    url = "{}?{}".format(path, query) if query else path
                    session.get(url)


def _validate_user_get_password(username, validate=True):
    if validate:
        user = WebUser.get_by_username(username)
        if not user:
            raise CommandError('User not found: {}'.format(username))

    password = getpass.getpass('Enter password for user {}:'.format(username))
    if validate and not user.get_django_user().check_password(password):
        raise CommandError("Password for user {} is incorrect".format(username))
    return password


def _get_authed_session(username, base_url, validate=True):
    password = _validate_user_get_password(username, validate)

    session = requests.session()
    login_url = '{}/accounts/login/'.format(base_url)

    # Pick up things like CSRF cookies and form fields by doing a GET first
    response = session.get(login_url)
    if response.status_code != 200:
        raise Exception(
            'Failed to connect to authentication page (%s): %s' % (response.status_code, response.text))

    response = session.post(
        login_url,
        headers={'Referer': login_url},
        data={
            'auth-username': username,
            'auth-password': _encode_password(password),
            'csrfmiddlewaretoken': response.cookies['csrftoken'],
            'hq_login_view-current_step': 'auth'
        },
        allow_redirects=False
    )

    if response.status_code != 302:
        raise Exception('Authentication failed {} ({}): {}'.format(login_url, response.status_code, response.text))

    return session


def _encode_password(password):
    """Apply password obfuscation"""
    def padding():
        return ''.join(random.sample(string.hexdigits, 6))

    padding_left = "sha256$" + padding()
    padding_right = padding() + "="

    def add_padding(val):
        return "{}{}{}".format(padding_left, val.decode('utf-8'), padding_right)

    secret = add_padding(base64.b64encode(password.encode('utf-8')))
    return add_padding(base64.b64encode(secret.encode('utf-8')))
