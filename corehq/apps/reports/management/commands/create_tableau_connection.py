import logging
from django.core.management import BaseCommand

from corehq.apps.reports.models import TableauAppConnection, TableauDomainDetails

logger = logging.getLogger('create_tableau_connection')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = ''' This command will associate a given set of domains with a Tableau connected app, enabling the use
              of Embedded Tableau on those domains. You can learn about creating a connected app here:
              https://help.tableau.com/current/server/en-us/connected_apps.htm#create-a-connected-app.'''

    def add_arguments(self, parser):
        parser.add_argument(
            '--domains',
            nargs='+',
            required=True,
            help="A list of domains to associate with the inputted connected app.",
        )
        parser.add_argument(
            '--server-name',
            required=True,
            help="The host name of the server that is running Tableau.",
        )
        parser.add_argument(
            '--site-name',
            required=True,
            help="The Tableau site you wish to connect your domain(s) with.",
        )
        parser.add_argument(
            '--app-client-id',
            required=True,
            help='''The unique ID for the connected app.'''
        )
        parser.add_argument(
            '--secret-id',
            required=True,
            help='''The ID of a secret generated for the connected app. See:
                 https://help.tableau.com/current/server/en-us/connected_apps.htm#step-2-generate-a-secret'''
        )
        parser.add_argument(
            '--secret-value',
            required=True,
            help="The value of a secret generated for the connected app.",
        )

    def handle(self, **options):
        self.options = options
        self.server_name, self.site_name, self.domains, self.app_client_id, self.secret_id, self.secret_value = \
            self.options['server_name'], self.options['site_name'], self.options['domains'], \
            self.options['app_client_id'], self.options['secret_id'], self.options['secret_value']

        app_connection = None
        try:
            app_connection = TableauAppConnection.objects.get(server_name=self.server_name,
                site_name=self.site_name, app_client_id=self.app_client_id)
            overwrite_secret = input("This connected app has been recognized in HQ. Want to overwrite the "
                                     "ID and value for the existing stored secret? (y/n)")
            if overwrite_secret == 'y':
                app_connection.secret_id = self.secret_id
                app_connection.plaintext_secret_value = self.secret_value
                app_connection.save()
                logger.info("The secret for the connected app has been updated!")
            else:
                logger.info("The secret will not be updated. The inputted domains will be associated with this "
                            "recognized connected app.")
        except TableauAppConnection.DoesNotExist:
            app_connection = TableauAppConnection(
                server_name=self.server_name,
                site_name=self.site_name,
                app_client_id=self.app_client_id,
                secret_id=self.secret_id,
            )
            app_connection.plaintext_secret_value = self.secret_value
            app_connection.save()
            logger.info("The connected app with its secret details are now stored in HQ.")

        logger.info("Associating each domain with the connected app...")
        for domain in self.options['domains']:
            try:
                domain_connection = TableauDomainDetails.objects.get(domain=domain)
                if domain_connection.app_connection == app_connection:
                    logger.info(f"FYI: Domain '{domain}' is already associated with this app. Moving on...")
                else:
                    overwrite_domain_connection = input(
                        f"Domain '{domain}' is already associated with a connected app with the following "
                        f"""details:
                            \nTableau server name: {domain_connection.app_connection.server_name}
                            \nTableau site name: {domain_connection.app_connection.site_name}
                            \nApp client ID: {domain_connection.app_connection.app_client_id}
                            \nDo you want to overwrite the connected app for this domain? (y/n)""")
                    if overwrite_domain_connection == 'y':
                        domain_connection.app_connection = app_connection
                        domain_connection.save()
                        logger.info(f"Domain '{domain}' is now associated with the inputted connected app.")
                    else:
                        logger.info(f"Domain '{domain}' will not be updated.")
            except TableauDomainDetails.DoesNotExist:
                TableauDomainDetails.objects.create(
                    domain=domain,
                    app_connection=app_connection
                )
                logger.info(f"Domain '{domain}' is now associated with the inputted connected app.")
        logger.info("Command execution completed.")
