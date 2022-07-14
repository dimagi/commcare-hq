import json
import logging
import requests
from django.core.management import BaseCommand

from corehq.apps.reports.models import TableauConnection

from settings import HQ_ACCOUNT_ROOT

logger = logging.getLogger('create_tableau_connection')
logger.setLevel('DEBUG')


class RequestFailure(Exception):
    pass


TABLEAU_CONNECTED_APP_NAME = "commcarehq_embedding"
DOMAIN_SAFE_LIST = [f"https://{HQ_ACCOUNT_ROOT}", f"https://staging.{HQ_ACCOUNT_ROOT}"]


class Command(BaseCommand):
    help = '''Creates a new TableauConnection and Tableau Connected App for a domain, enabling
              the use of Embedded Tableau. The Tableau Connected App will have the reserved name
              "commcarehq_embedding".'''
    # Utilizes the Tableau API: https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api.htm

    def add_arguments(self, parser):
        parser.add_argument(
            '--PAT-name',
            action='store',
            dest='pat_name',
            required=True,
            help="""The name of the Personal Access Token of a Server Admin on the Tableau site you want
                 to connect your domain to. To generate one, see here:
                 https://help.tableau.com/current/server/en-us/security_personal_access_tokens.htm#create-tokens
                 """,
        )
        parser.add_argument(
            '--PAT-secret',
            action='store',
            dest='pat_secret',
            required=True,
            help="The Personal Access Token secret.",
        )
        parser.add_argument(
            '--server-name',
            action='store',
            dest='server_name',
            required=True,
            help="The host name of the server that is running Tableau.",
        )
        parser.add_argument(
            '--site-name',
            action='store',
            dest='site_name',
            required=True,
            help="The Tableau site to create a connected app on.",
        )
        parser.add_argument(
            '--domain',
            action='store',
            dest='domain',
            required=True,
            help="The name of the domain to use connect the Tableau site to, for use with Embedded Tableau.",
        )

    def handle(self, **options):
        self.options = options
        self.server_name = self.options['server_name']
        self.site_name = self.options['site_name']
        self.domain = self.options['domain']

        api_version = 3.14  # Minimum version needed to use the method to create a connected app.
        self.url_base = f"https://{self.server_name}/api/{api_version}"

        # Without these headers, the Tableau API uses XML by default.
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # You must be signed into an authenticated account to create a Connected App with the Tableau API.
        self.sign_in()
        try:
            # The site ID is necessary for making site-specific API requests.
            self.site_id = self.get_site_id()
            (connected_app_exists, connected_app_client_id) = self.check_if_connected_app_exists()
            if connected_app_exists:
                overwrite = input("\nA CommCareHQ connected app already exists on this site. Overwrite and "
                                  "create a new one? [y/n]")
                if overwrite == 'y':
                    self.delete_existing_connected_app(connected_app_client_id)
                else:
                    logger.info("No app created. Command execution completed.")
                    self.sign_out()
                    return
            self.create_connected_app()
            logger.info("App succesffully created. Command execution completed.")
            self.sign_out()
        # I think it's ok to ignore the flake8 error for this bare except clause since we re-raise the exception.
        except:  # noqa: E722
            logger.info("Command execution interrupted.")
            # Submit a sign out request on any interruption to ensure the token we were given upon sign in is no
            # longer valid.
            self.sign_out()
            raise

    def sign_in(self):
        logger.info("Signing into the API so we can add a new connected app...")
        request_url = f"{self.url_base}/auth/signin"
        payload = {
            "credentials": {
                "personalAccessTokenName": self.options['pat_name'],
                "personalAccessTokenSecret": self.options['pat_secret'],
                "site": {
                    "contentUrl": self.site_name
                }
            }
        }
        response_body = self._process_response(
            response=requests.post(request_url, data=json.dumps(payload), headers=self.headers),
            custom_msg_if_failure="Request to sign in failed."
        )
        api_auth_token = response_body["credentials"]["token"]
        self.headers.update({"X-Tableau-Auth": api_auth_token})
        logger.info("Sign in successful.")

    def sign_out(self):
        logger.info('Signing out of the API...')
        try:
            self.request_sign_out()
            logger.info('Sign out request successful.')
        except RequestFailure as e:
            logger.info(e)

    def request_sign_out(self):
        request_url = f"{self.url_base}/auth/signout"
        self._process_response(
            response=requests.post(request_url, headers=self.headers),
            custom_msg_if_failure="Request to sign out failed.",
            returns_body=False
        )

    def get_site_id(self):
        request_url = f"{self.url_base}/sites/{self.site_name}?key=name"
        response_body = self._process_response(
            response=requests.get(request_url, headers=self.headers),
            custom_msg_if_failure="Request to get site ID from name failed."
        )
        return response_body["site"]["id"]

    def check_if_connected_app_exists(self):
        # Use the list apps api method to check if a connected app exists with the name 'commcarehq_embedding'.
        request_url = f"{self.url_base}/sites/{self.site_id}/connected-applications"
        response_body = self._process_response(
            response=requests.get(request_url, headers=self.headers),
            custom_msg_if_failure="Request to check if a connected app already exists failed."
        )
        if response_body["connectedApplications"]:
            connected_apps = response_body["connectedApplications"]["connectedApplication"]
            for app in connected_apps:
                if app["name"] == "commcarehq_embedding":
                    return (True, app["clientId"])

        return (False, None)

    def delete_existing_connected_app(self, connected_app_client_id):
        request_url = f"{self.url_base}/sites/{self.site_id}/connected-applications/{connected_app_client_id}"
        self._process_response(
            response=requests.delete(request_url, headers=self.headers),
            custom_msg_if_failure="Request to delete the existing connected app failed.",
            returns_body=False
        )

    def create_connected_app(self):

        # 1. Create a connected app on the Tableau site.
        request_url = f"{self.url_base}/sites/{self.site_id}/connected-applications"
        payload = {
            "connectedApplication": {
                "name": TABLEAU_CONNECTED_APP_NAME,
                "enabled": "true",
                "domainSafelist": ' '.join(DOMAIN_SAFE_LIST),
                "unrestrictedEmbedding": "false"
            }
        }
        response_body = self._process_response(
            response=requests.post(request_url, data=json.dumps(payload), headers=self.headers),
            custom_msg_if_failure="Request to create a connected app failed."
        )
        app_client_id = response_body["connectedApplication"]["clientId"]

        # 2. Create a secret for the connected app.
        request_url = f"{self.url_base}/sites/{self.site_id}/connected-applications/{app_client_id}/secrets"
        response_body = self._process_response(
            response=requests.post(request_url, headers=self.headers),
            custom_msg_if_failure="Request to create a secret for the connected app failed."
        )
        secret_value = response_body["connectedApplicationSecret"]["value"]

        # 3. Store the secret in a TableauConnection object.
        try:
            TableauConnection.objects.get(domain=self.domain)
        except TableauConnection.DoesNotExist:
            TableauConnection.objects.create(
                domain=self.domain,
                server_name=self.server_name,
                site_name=self.site_name,
                secret=secret_value
            )

    def _process_response(self, response, custom_msg_if_failure="Request failed.", returns_body=True):
        if response.ok:
            if returns_body:
                return json.loads(response.text)
        else:
            raise RequestFailure(f'{custom_msg_if_failure}'
                                 f'\nResponse code: {response.status_code}'
                                 f'\nError message: {response.text}')
