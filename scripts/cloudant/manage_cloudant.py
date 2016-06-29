"""
See https://cloudant.com/for-developers/faq/auth/ for cloudant reference
"""
from collections import namedtuple
from getpass import getpass
import requests

Auth = namedtuple('Auth', 'username password')


class CloudantInstance(Auth):

    def create_database(self, db_name):
        return CloudantDatabase(self, db_name).create()

    def database_exists(self, db_name):
        return CloudantDatabase(self, db_name).exists()

    def get_db(self, db_name):
        return CloudantDatabase(self, db_name)

    def generate_api_key(self, ask=True):
        if ask:
            ask_user('Generating new API key for {}'.format(self.username))
        new_api_key_response = requests.post(
            'https://{username}.cloudant.com/_api/v2/api_keys'.format(username=self.username),
            auth=self).json()
        assert new_api_key_response['ok'] is True
        return Auth(new_api_key_response['key'], new_api_key_response['password'])


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

    def create(self, ask=True):
        db_uri = self._get_db_uri()
        if ask:
            ask_user('Creating database {}'.format(db_uri))

        response = requests.put(db_uri, auth=self.instance).json()
        print response

    def exists(self):
        db_uri = self._get_db_uri()
        status_code = requests.get(db_uri, auth=self.instance).status_code
        return status_code == 200

    def grant_api_key_access(self, api_key, ask=True):
        db_uri = self._get_db_uri()
        security_url = self._get_security_url()
        security = requests.get(security_url, auth=self.instance).json()
        assert api_key
        if ask:
            ask_user('Granting api_key {} access to database {}'.format(api_key, db_uri))
        if not security:
            security = {'cloudant': {}}
        security['cloudant'][api_key] = ["_admin", "_reader", "_writer", "_replicator"]

        security = requests.put(security_url, auth=self.instance, json=security).json()
        print security

    def revoke_api_key_access(self, api_key, ask=True):
        db_uri = self._get_db_uri()
        security_url = self._get_security_url()
        security = requests.get(security_url, auth=self.instance).json()
        assert api_key
        if ask:
            ask_user('Revoking api_key {} access to database {}'.format(api_key, db_uri))
        if not security:
            security = {'cloudant': {}}
        if api_key in security['cloudant']:
            del security['cloudant'][api_key]

        security = requests.put(security_url, auth=self.instance, json=security).json()
        print security


def get_cloudant_password(username):
    print 'Provide password for Cloudant user {}'.format(username)
    return getpass()


def ask_user(statement):
    y = raw_input('{}. Ok? (y/n)'.format(statement))
    if y != 'y':
        print 'Aborting'
        exit(0)


def authenticate_cloudant_instance(username):
    return CloudantInstance(username, get_cloudant_password(username))
