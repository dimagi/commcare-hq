import argparse
import csv
import gzip
from textwrap import dedent

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.models import Domain
from corehq.util.argparse_types import date_type

from ...utils.export import get_users_for_domain, write_log_events


class Command(BaseCommand):

    help = dedent("""\
        Generate request report of NavigationEventAudit events

        NOTES
            - AccessAudit events are not included in this report.
            - All filtering options are AND'd together (important to consider when
              combining both --user and --domain options).
            - Specifying the --domain option excludes all non-domain navigation events
              (admin activities, account/profile management, etc).
            - Specifying the --domain option without the --user option will result in a
              report limited to "users associated with that domain" (not including
              enterprise users) and superusers.
    """)

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        # cannot add `formatter_class` to kwargs because BaseCommand will specify it twice
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument('filename', help="Output file path")
        parser.add_argument('-z', '--gzip', action="store_true", default=False,
            help="gzip-compress the output")
        parser.add_argument('-d', '--domain', dest='domain',
                            help="Limit logs to only this domain (can be multiple separated by commas)")
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
        username = options["user"]
        display_superuser = options["display_superuser"]

        dimagi_username = ""
        if not display_superuser:
            dimagi_username = "Dimagi Support"

        if not domain and not username:
            raise CommandError("Please provide one of 'domain' or 'username'")

        if domain:
            domains = domain.split(',')
            for domain in domains:
                domain_object = Domain.get_by_name(domain)
                if not domain_object:
                    raise CommandError("Domain not found")

        user_lists_by_domain = {}
        for domain in domains:
            if username:
                users, removed_users, super_users = [username], [], []
            else:
                users, removed_users, super_users = get_users_for_domain(domain)
            user_lists_by_domain[domain] = (users, removed_users, super_users)

        if options["gzip"]:
            opener = gzip.open
        else:
            opener = open

        with opener(filename, "wt") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Date', 'User', 'Domain', 'IP Address', 'Request Method', 'Request Path'])
            for domain, (users, removed_users, super_users) in user_lists_by_domain.items():
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
