import csv

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.models import Domain
from corehq.util.argparse_types import date_type

from ...utils.export import get_users_to_export, write_log_events


class Command(BaseCommand):
    help = """Generate request report"""

    def add_arguments(self, parser):
        parser.add_argument('filename', help="Output file path")
        parser.add_argument('-d', '--domain', dest='domain', help="Limit logs to only this domain")
        parser.add_argument('-u', '--user', dest='user', help="Limit logs to only this user")
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=date_type,
            help="The start date - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=date_type,
            help="The end date - format YYYY-MM-DD",
        )
        parser.add_argument(
            '--display-superuser',
            action='store_true',
            dest='display_superuser',
            default=False,
            help="Include superusers in report, otherwise 'Dimagi Support'",
        )

    def handle(self, filename, **options):
        domain = options["domain"]
        user = options["user"]
        display_superuser = options["display_superuser"]

        dimagi_username = ""
        if not display_superuser:
            dimagi_username = "Dimagi Support"

        if not domain and not user:
            raise CommandError("Please provide one of 'domain' or 'user'")

        if domain:
            domain_object = Domain.get_by_name(domain)
            if not domain_object:
                raise CommandError("Domain not found")

        users, removed_users, super_users = get_users_to_export(user, domain)

        with open(filename, 'w') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Date', 'User', 'Domain', 'IP Address', 'Request Path'])
            for user in users:
                write_log_events(writer, user, domain, start_date=options['start'], end_date=options['end'])

            for user in removed_users:
                write_log_events(
                    writer,
                    user,
                    domain,
                    override_user=f"{user} [REMOVED]",
                    start_date=options['start'],
                    end_date=options['end']
                )

            for user in super_users:
                write_log_events(
                    writer,
                    user,
                    domain,
                    override_user=dimagi_username,
                    start_date=options['start'],
                    end_date=options['end']
                )
