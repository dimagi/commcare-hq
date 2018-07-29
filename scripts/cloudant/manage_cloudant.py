"""
See https://cloudant.com/for-developers/faq/auth/ for cloudant reference
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from getpass import getpass
import requests
from six.moves import input

Auth = namedtuple('Auth', 'username password')


class AskRun(namedtuple('AskRun', 'ask run')):
    def ask_and_run(self):
        ask_user(self.ask())
        return self.run()


class CloudantInstance(Auth):

    def create_database(self, db_name):
        return CloudantDatabase(self, db_name).create()

    def database_exists(self, db_name):
        return CloudantDatabase(self, db_name).exists()

    def get_db(self, db_name):
        return CloudantDatabase(self, db_name)

    def generate_api_key(self):
        def ask():
            return 'Generating new API key for {}'.format(self.username)

        def run():
            new_api_key_response = requests.post(
                'https://{username}.cloudant.com/_api/v2/api_keys'.format(username=self.username),
                auth=self).json()
            assert new_api_key_response['ok'] is True
            return Auth(new_api_key_response['key'], new_api_key_response['password'])

        return AskRun(ask, run)


class CloudantDatabase(namedtuple('CloudantInstance', 'instance db_name')):
    def _get_db_uri(self):
        return (
            'https://{username}.cloudant.com/{database}'
            .format(username=self.instance.username, database=self.db_name)
        )

    def _get_security_url(self):
        return (
            'https://{username}.cloudant.com/_api/v2/db/{database}/_security'
            .format(username=self.instance.username, database=self.db_name)
        )

    def create(self):
        db_uri = self._get_db_uri()

        def ask():
            return 'Creating database {}'.format(db_uri)

        def run():
            return requests.put(db_uri, auth=self.instance).json()

        return AskRun(ask, run)

    def exists(self):
        db_uri = self._get_db_uri()
        status_code = requests.get(db_uri, auth=self.instance).status_code
        return status_code == 200

    def grant_api_key_access(self, api_key, admin=False):
        db_uri = self._get_db_uri()
        security_url = self._get_security_url()
        security = requests.get(security_url, auth=self.instance).json()
        assert api_key

        if not security:
            security = {'cloudant': {}}
        if admin:
            permissions = ["_admin", "_reader", "_writer", "_replicator"]
        else:
            permissions = ["_reader"]
        security['cloudant'][api_key] = permissions

        def ask():
            return ('Granting api_key {} access with permissions {} to database {}'
                    .format(api_key, ' '.join(permissions), db_uri))

        def run():
            return requests.put(security_url, auth=self.instance, json=security).json()

        return AskRun(ask, run)

    def revoke_api_key_access(self, api_key):
        db_uri = self._get_db_uri()
        security_url = self._get_security_url()
        security = requests.get(security_url, auth=self.instance).json()
        assert api_key

        if not security:
            security = {'cloudant': {}}

        if api_key in security['cloudant']:
            del security['cloudant'][api_key]

        def ask():
            return 'Revoking api_key {} access to database {}'.format(api_key, db_uri)

        def run():
            return requests.put(security_url, auth=self.instance, json=security).json()

        return AskRun(ask, run)


def get_cloudant_password(username):
    print('Provide password for Cloudant user {}'.format(username))
    return getpass()


def ask_user(statement):
    y = input('{}. Ok? (y/n)'.format(statement))
    if y != 'y':
        print('Aborting')
        exit(0)


def run_ask_runs(ask_runs):
    for ask_run in ask_runs:
        print(ask_run.ask())
    ask_user('The preceding steps will be performed')
    for ask_run in ask_runs:
        print(ask_run.run())


def authenticate_cloudant_instance(username):
    return CloudantInstance(username, get_cloudant_password(username))
